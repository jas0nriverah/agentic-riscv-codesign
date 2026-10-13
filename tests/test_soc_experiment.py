"""Guard against silently reverting the SoC experiment to external memory."""
from copy import deepcopy

import pytest

from isaforge.core_experiment import SUCCESS, crc32_oracle
from isaforge.soc_experiment import EXPECTED_PORTS, compare_prior_firmware, memory_image, validate_netlist, validate_soc_measurement


def netlist_fixture():
    ports = {name: dict(direction=direction, bits=[2 if name == "clk" else index + 3])
             for index, (name, direction) in enumerate(EXPECTED_PORTS.items())}
    cells = {f"memory.0.{i}": dict(type="SB_RAM40_4K", connections={"RCLK": [2], "WCLK": [2]}) for i in range(16)}
    cells.update({f"cpu.cpuregs.{i}": dict(type="SB_RAM40_4K", connections={"RCLK": [2], "WCLK": [2]}) for i in range(4)})
    cells["logic"] = dict(type="SB_LUT4")
    return dict(modules=dict(soc_top=dict(ports=ports, cells=cells)))


def measurement_fixture():
    count = 172 * 1024 * 2
    return dict(status=SUCCESS, fault=0, partial_report_bits=0,
                words=[crc32_oracle(), 11433, 29602102, 5572292, 1],
                pcpi_handshakes=count, pcpi_valid_cycles=count, pcpi_wait_cycles=0)


def test_memory_image_endianness_zero_fill_and_stack_reservation():
    rows = memory_image(b"\x01\x02\x03\x04\xdd").splitlines()
    assert len(rows) == 2048
    assert rows[:2] == ["04030201", "000000dd"]
    assert all(row == "00000000" for row in rows[2:])
    assert len(memory_image(bytes(4096)).splitlines()) == 2048
    with pytest.raises(ValueError, match="reserve"):
        memory_image(bytes(4097))


def test_prior_firmware_changes_only_stack_instruction():
    previous = (0x00010137).to_bytes(4, "little") + b"same rest of binary"
    current = (0x00002137).to_bytes(4, "little") + b"same rest of binary"
    assert compare_prior_firmware(current, previous)["all_other_binary_bytes_identical"]
    with pytest.raises(ValueError, match="only in the initial stack"):
        compare_prior_firmware(current[:-1] + b"x", previous)
    with pytest.raises(ValueError, match="only in the initial stack"):
        compare_prior_firmware((0x00003137).to_bytes(4, "little") + current[4:], previous)


def test_closed_memory_clocked_netlist_fits_counts():
    result = validate_netlist(netlist_fixture())
    assert result["memory_blocks"] == 20
    assert result["program_data_memory_blocks"] == 16
    assert result["all_bram_clocks_use_top_clock"]
    assert len(result["top_ports"]) == 8


@pytest.mark.parametrize("fault", ["external_port", "vector_port", "ram_not_inferred", "wrong_clock", "oversized_luts", "missing_program_ram"])
def test_rejects_invalid_soc_synthesis(fault):
    netlist = netlist_fixture()
    top = netlist["modules"]["soc_top"]
    if fault == "external_port":
        top["ports"]["mem_ready"] = dict(direction="input", bits=[99])
    elif fault == "vector_port":
        top["ports"]["report_bit"]["bits"].append(99)
    elif fault == "ram_not_inferred":
        top["cells"] = {}
    elif fault == "wrong_clock":
        top["cells"]["memory.0.0"]["connections"]["RCLK"] = [99]
    elif fault == "oversized_luts":
        top["cells"].update({f"logic{i}": dict(type="SB_LUT4") for i in range(7680)})
    elif fault == "missing_program_ram":
        top["cells"]["renamed"] = top["cells"].pop("memory.0.0")
    with pytest.raises(ValueError):
        validate_netlist(netlist)


def test_soc_requires_full_crc_checksum_and_complete_pin_report():
    assert validate_soc_measurement(measurement_fixture(), 3)["self_check_passed"]
    for fault in ("fault", "partial_report_bits", "pcpi_wait_cycles"):
        bad = measurement_fixture()
        bad[fault] = 1
        with pytest.raises(ValueError):
            validate_soc_measurement(bad, 3)
    wrong = measurement_fixture()
    wrong["words"][0] ^= 0x80000000
    with pytest.raises(ValueError, match="full CRC32"):
        validate_soc_measurement(wrong, 3)
    wrong = deepcopy(measurement_fixture())
    wrong["pcpi_valid_cycles"] += 1
    with pytest.raises(ValueError, match="combinational response"):
        validate_soc_measurement(wrong, 3)
