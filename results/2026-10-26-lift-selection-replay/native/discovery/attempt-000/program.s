	.file	"program.c"
	.option nopic
	.option norelax
	.attribute arch, "rv32i2p1_zicsr2p0"
	.attribute unaligned_access, 0
	.attribute stack_align, 16
	.text
	.section	.text.lift_return,"ax",@progbits
	.align	2
	.globl	lift_return
	.type	lift_return, @function
lift_return:
	lui	a5,%hi(lift_checksum)
	lw	a0,%lo(lift_checksum)(a5)
	li	a5,-4005888
	add	a0,a0,a5
	snez	a0,a0
	ret
	.size	lift_return, .-lift_return
	.section	.text.lift_io_init,"ax",@progbits
	.align	2
	.globl	lift_io_init
	.type	lift_io_init, @function
lift_io_init:
	lui	a5,%hi(lift_ctrl_dly1)
	sw	zero,%lo(lift_ctrl_dly1)(a5)
	lui	a5,%hi(lift_ctrl_dly2)
	sw	zero,%lo(lift_ctrl_dly2)(a5)
	ret
	.size	lift_io_init, .-lift_io_init
	.section	.text.lift_ctrl_set_vals,"ax",@progbits
	.align	2
	.globl	lift_ctrl_set_vals
	.type	lift_ctrl_set_vals, @function
lift_ctrl_set_vals:
	lui	a4,%hi(lift_ctrl_io_out)
	addi	a4,a4,%lo(lift_ctrl_io_out)
	addi	a2,a4,-16
	li	a5,0
.L4:
	lw	a3,12(a4)
	slli	a5,a5,1
	addi	a4,a4,-4
	snez	a3,a3
	or	a5,a3,a5
	bne	a2,a4,.L4
	lui	a4,%hi(lift_simio_out)
	sw	a5,%lo(lift_simio_out)(a4)
	lui	a4,%hi(lift_ctrl_io_led)
	addi	a4,a4,%lo(lift_ctrl_io_led)
	addi	a2,a4,-56
.L5:
	lw	a3,52(a4)
	slli	a5,a5,1
	addi	a4,a4,-4
	snez	a3,a3
	or	a5,a3,a5
	bne	a2,a4,.L5
	lui	a4,%hi(lift_simio_led)
	lui	a3,%hi(lift_checksum)
	sw	a5,%lo(lift_simio_led)(a4)
	lw	a4,%lo(lift_checksum)(a3)
	add	a5,a4,a5
	sw	a5,%lo(lift_checksum)(a3)
	ret
	.size	lift_ctrl_set_vals, .-lift_ctrl_set_vals
	.section	.text.lift_ctrl_get_vals,"ax",@progbits
	.align	2
	.globl	lift_ctrl_get_vals
	.type	lift_ctrl_get_vals, @function
lift_ctrl_get_vals:
	lui	a5,%hi(lift_simio_in)
	lw	a3,%lo(lift_simio_in)(a5)
	lui	a5,%hi(lift_ctrl_dly1)
	lw	a0,%lo(lift_ctrl_dly1)(a5)
	lui	a4,%hi(lift_ctrl_dly2)
	lhu	a2,%lo(lift_ctrl_dly2)(a4)
	slli	a3,a3,16
	sw	a0,%lo(lift_ctrl_dly2)(a4)
	lui	a4,%hi(lift_ctrl_io_in)
	slli	a1,a0,16
	srli	a3,a3,16
	addi	a4,a4,%lo(lift_ctrl_io_in)
	srli	a1,a1,16
	sw	a3,%lo(lift_ctrl_dly1)(a5)
	addi	a0,a4,40
.L9:
	andi	a6,a1,1
	andi	a5,a3,1
	add	a5,a5,a6
	andi	a6,a2,1
	add	a5,a5,a6
	slti	a5,a5,2
	seqz	a5,a5
	sw	a5,0(a4)
	addi	a4,a4,4
	srli	a3,a3,1
	srli	a1,a1,1
	srli	a2,a2,1
	bne	a0,a4,.L9
	lui	a5,%hi(lift_simio_adc1)
	lw	a4,%lo(lift_simio_adc1)(a5)
	lui	a5,%hi(lift_ctrl_io_analog)
	addi	a5,a5,%lo(lift_ctrl_io_analog)
	sw	a4,0(a5)
	lui	a4,%hi(lift_simio_adc2)
	lw	a4,%lo(lift_simio_adc2)(a4)
	sw	a4,4(a5)
	lui	a4,%hi(lift_simio_adc3)
	lw	a4,%lo(lift_simio_adc3)(a4)
	sw	a4,8(a5)
	ret
	.size	lift_ctrl_get_vals, .-lift_ctrl_get_vals
	.section	.text.lift_ctrl_init,"ax",@progbits
	.align	2
	.globl	lift_ctrl_init
	.type	lift_ctrl_init, @function
lift_ctrl_init:
	addi	sp,sp,-16
	lui	a5,%hi(lift_checksum)
	sw	ra,12(sp)
	sw	zero,%lo(lift_checksum)(a5)
	call	lift_io_init
	lui	a5,%hi(lift_cntValid)
	sw	zero,%lo(lift_cntValid)(a5)
	lui	a5,%hi(lift_cnt)
	sw	zero,%lo(lift_cnt)(a5)
	lui	a5,%hi(lift_cmd)
	sw	zero,%lo(lift_cmd)(a5)
	lui	a5,%hi(lift_timMotor)
	sw	zero,%lo(lift_timMotor)(a5)
	lui	a5,%hi(lift_timImp)
	sw	zero,%lo(lift_timImp)(a5)
	li	a4,1
	lui	a5,%hi(lift_directionUp)
	sw	a4,%lo(lift_directionUp)(a5)
	lui	a5,%hi(lift_lastImp)
	sw	zero,%lo(lift_lastImp)(a5)
	lui	a5,%hi(lift_loadLevel)
	sw	zero,%lo(lift_loadLevel)(a5)
	lui	a5,%hi(lift_loadPending)
	sw	zero,%lo(lift_loadPending)(a5)
	lui	a5,%hi(lift_loadSensor)
	sw	zero,%lo(lift_loadSensor)(a5)
	lui	a5,%hi(lift_levelPos)
	addi	a5,a5,%lo(lift_levelPos)
	li	a3,115
	sw	a3,8(a5)
	li	a3,173
	sw	a3,12(a5)
	li	a3,230
	sw	a3,16(a5)
	li	a3,288
	sw	a3,20(a5)
	li	a3,346
	sw	a3,24(a5)
	li	a3,403
	sw	a3,28(a5)
	li	a3,461
	sw	a3,32(a5)
	li	a3,518
	sw	a3,36(a5)
	li	a3,576
	sw	a3,40(a5)
	li	a3,634
	sw	a3,44(a5)
	li	a3,691
	sw	a3,48(a5)
	li	a3,749
	sw	a3,52(a5)
	li	a3,806
	sw	a3,56(a5)
	lw	ra,12(sp)
	li	a4,58
	li	a3,864
	sw	zero,0(a5)
	sw	a4,4(a5)
	sw	a3,60(a5)
	lui	a5,%hi(lift_one_level)
	sw	a4,%lo(lift_one_level)(a5)
	addi	sp,sp,16
	jr	ra
	.size	lift_ctrl_init, .-lift_ctrl_init
	.section	.text.lift_init,"ax",@progbits
	.align	2
	.globl	lift_init
	.type	lift_init, @function
lift_init:
	addi	sp,sp,-16
	lui	a5,%hi(lift_ctrl_io_in)
	lui	a4,%hi(lift_ctrl_io_in+40)
	sb	zero,15(sp)
	addi	a5,a5,%lo(lift_ctrl_io_in)
	addi	a4,a4,%lo(lift_ctrl_io_in+40)
.L14:
	lbu	a2,0(a5)
	lbu	a3,15(sp)
	addi	a5,a5,1
	xor	a3,a3,a2
	sb	a3,-1(a5)
	bne	a5,a4,.L14
	lui	a5,%hi(lift_ctrl_io_out)
	lui	a4,%hi(lift_ctrl_io_out+16)
	addi	a5,a5,%lo(lift_ctrl_io_out)
	addi	a4,a4,%lo(lift_ctrl_io_out+16)
.L15:
	lbu	a2,0(a5)
	lbu	a3,15(sp)
	addi	a5,a5,1
	xor	a3,a3,a2
	sb	a3,-1(a5)
	bne	a5,a4,.L15
	lui	a5,%hi(lift_ctrl_io_analog)
	lui	a4,%hi(lift_ctrl_io_analog+16)
	addi	a5,a5,%lo(lift_ctrl_io_analog)
	addi	a4,a4,%lo(lift_ctrl_io_analog+16)
.L16:
	lbu	a2,0(a5)
	lbu	a3,15(sp)
	addi	a5,a5,1
	xor	a3,a3,a2
	sb	a3,-1(a5)
	bne	a5,a4,.L16
	lui	a5,%hi(lift_ctrl_io_led)
	lui	a4,%hi(lift_ctrl_io_led+64)
	addi	a5,a5,%lo(lift_ctrl_io_led)
	addi	a4,a4,%lo(lift_ctrl_io_led+64)
.L17:
	lbu	a2,0(a5)
	lbu	a3,15(sp)
	addi	a5,a5,1
	xor	a3,a3,a2
	sb	a3,-1(a5)
	bne	a5,a4,.L17
	lui	a5,%hi(lift_checksum)
	sw	zero,%lo(lift_checksum)(a5)
	addi	sp,sp,16
	tail	lift_ctrl_init
	.size	lift_init, .-lift_init
	.section	.text.lift_check_level,"ax",@progbits
	.align	2
	.globl	lift_check_level
	.type	lift_check_level, @function
lift_check_level:
	lui	a5,%hi(lift_cntValid)
	lw	a5,%lo(lift_cntValid)(a5)
	lui	a4,%hi(lift_level)
	beq	a5,zero,.L24
	lui	a5,%hi(lift_one_level)
	lw	a1,%lo(lift_one_level)(a5)
	lui	a3,%hi(lift_cnt)
	lw	a7,%lo(lift_cnt)(a3)
	li	a5,1
	lui	a3,%hi(lift_levelPos)
	srai	a1,a1,2
	sw	a5,%lo(lift_level)(a4)
	addi	a3,a3,%lo(lift_levelPos)
	li	a2,0
	li	a6,14
.L25:
	beq	a5,a6,.L38
	lw	a0,4(a3)
	addi	a3,a3,4
	sub	a0,a0,a1
	ble	a0,a7,.L29
.L38:
	beq	a2,zero,.L26
	sw	a5,%lo(lift_level)(a4)
.L26:
	lw	a2,%lo(lift_level)(a4)
	lui	a5,%hi(lift_ctrl_io_led)
	addi	a5,a5,%lo(lift_ctrl_io_led)
	addi	a2,a2,-1
	li	a4,0
	li	a1,14
.L28:
	sub	a3,a2,a4
	seqz	a3,a3
	sw	a3,0(a5)
	addi	a4,a4,1
	addi	a5,a5,4
	bne	a4,a1,.L28
	ret
.L29:
	addi	a5,a5,1
	li	a2,1
	j	.L25
.L24:
	sw	zero,%lo(lift_level)(a4)
	j	.L26
	.size	lift_check_level, .-lift_check_level
	.section	.text.lift_check_cmd,"ax",@progbits
	.align	2
	.globl	lift_check_cmd
	.type	lift_check_cmd, @function
lift_check_cmd:
	lui	a3,%hi(lift_loadPending)
	lw	a2,%lo(lift_loadPending)(a3)
	lui	a5,%hi(lift_ctrl_io_in)
	addi	a5,a5,%lo(lift_ctrl_io_in)
	lui	a4,%hi(lift_cmd)
	beq	a2,zero,.L40
	lw	a5,8(a5)
	beq	a5,zero,.L41
.L48:
	li	a5,1
.L62:
	sw	a5,%lo(lift_cmd)(a4)
.L42:
	lui	a5,%hi(lift_timMotor)
	li	a4,50
	sw	a4,%lo(lift_timMotor)(a5)
	ret
.L40:
	lw	a2,16(a5)
	beq	a2,zero,.L43
	lw	a5,4(a5)
	bne	a5,zero,.L41
	lui	a5,%hi(lift_level)
	lw	a3,%lo(lift_level)(a5)
	li	a5,14
	beq	a3,a5,.L41
	li	a5,3
	j	.L62
.L43:
	lw	a2,20(a5)
	beq	a2,zero,.L44
	lw	a5,8(a5)
	bne	a5,zero,.L41
	lui	a5,%hi(lift_level)
	lw	a3,%lo(lift_level)(a5)
	li	a5,1
	beq	a3,a5,.L41
	li	a5,4
	j	.L62
.L44:
	lw	a2,32(a5)
	beq	a2,zero,.L45
	lui	a5,%hi(lift_loadLevel)
	lw	a5,%lo(lift_loadLevel)(a5)
	li	a2,2
	beq	a5,zero,.L46
	lui	a2,%hi(lift_level)
	lw	a2,%lo(lift_level)(a2)
	sgt	a5,a5,a2
	seqz	a5,a5
	addi	a2,a5,1
.L46:
	li	a5,1
	sw	a5,%lo(lift_loadPending)(a3)
	lui	a5,%hi(lift_loadSensor)
	sw	a2,%lo(lift_cmd)(a4)
	sw	zero,%lo(lift_loadSensor)(a5)
	j	.L42
.L45:
	lw	a3,24(a5)
	beq	a3,zero,.L47
	lw	a5,4(a5)
	beq	a5,zero,.L48
.L41:
	lw	a5,%lo(lift_cmd)(a4)
	bne	a5,zero,.L42
	ret
.L47:
	lw	a3,28(a5)
	beq	a3,zero,.L41
	lw	a5,8(a5)
	bne	a5,zero,.L41
	li	a5,2
	j	.L62
	.size	lift_check_cmd, .-lift_check_cmd
	.section	.text.lift_do_impulse,"ax",@progbits
	.align	2
	.globl	lift_do_impulse
	.type	lift_do_impulse, @function
lift_do_impulse:
	lui	a6,%hi(lift_timImp)
	lw	a5,%lo(lift_timImp)(a6)
	lui	a7,%hi(lift_lastImp)
	beq	a0,zero,.L64
	lw	a4,%lo(lift_lastImp)(a7)
	bne	a4,zero,.L64
	bne	a1,zero,.L65
	ble	a5,zero,.L64
.L65:
	lui	a1,%hi(lift_directionUp)
	lw	a1,%lo(lift_directionUp)(a1)
	lui	a3,%hi(lift_cnt)
	lw	a4,%lo(lift_cnt)(a3)
	beq	a1,zero,.L66
	addi	a4,a4,1
.L80:
	sw	a4,%lo(lift_cnt)(a3)
.L64:
	beq	a2,zero,.L67
	lui	a4,%hi(lift_cnt)
	sw	zero,%lo(lift_cnt)(a4)
	li	a3,1
	lui	a4,%hi(lift_cntValid)
	sw	a3,%lo(lift_cntValid)(a4)
.L67:
	sw	a0,%lo(lift_lastImp)(a7)
	ble	a5,zero,.L63
	addi	a5,a5,-1
	sw	a5,%lo(lift_timImp)(a6)
	bne	a5,zero,.L63
	lui	a5,%hi(lift_cmd)
	lw	a4,%lo(lift_cmd)(a5)
	beq	a4,zero,.L63
	sw	zero,%lo(lift_cmd)(a5)
.L63:
	ret
.L66:
	addi	a4,a4,-1
	j	.L80
	.size	lift_do_impulse, .-lift_do_impulse
	.section	.text.lift_wait_for_motor_start,"ax",@progbits
	.align	2
	.globl	lift_wait_for_motor_start
	.type	lift_wait_for_motor_start, @function
lift_wait_for_motor_start:
	lui	a4,%hi(lift_timMotor)
	lw	a5,%lo(lift_timMotor)(a4)
	lui	a3,%hi(lift_directionUp)
	addi	a5,a5,-1
	sw	a5,%lo(lift_timMotor)(a4)
	lui	a5,%hi(lift_cmd)
	lw	a4,%lo(lift_cmd)(a5)
	andi	a5,a4,-3
	addi	a5,a5,-1
	seqz	a5,a5
	sw	a5,%lo(lift_directionUp)(a3)
	lui	a3,%hi(lift_ctrl_io_out+4)
	sw	a5,%lo(lift_ctrl_io_out+4)(a3)
	lui	a5,%hi(lift_cntValid)
	lw	a2,%lo(lift_cntValid)(a5)
	lui	a3,%hi(lift_endCnt)
	lui	a5,%hi(lift_cnt)
	bne	a2,zero,.L82
	sw	zero,%lo(lift_cnt)(a5)
	li	a2,3
	lui	a5,%hi(lift_one_level)
	lw	a5,%lo(lift_one_level)(a5)
	bne	a4,a2,.L83
.L87:
	sw	a5,%lo(lift_endCnt)(a3)
.L81:
	ret
.L83:
	neg	a5,a5
	j	.L87
.L82:
	lw	a5,%lo(lift_cnt)(a5)
	sw	a5,%lo(lift_endCnt)(a3)
	li	a5,3
	bne	a4,a5,.L85
	lui	a5,%hi(lift_level)
	lw	a5,%lo(lift_level)(a5)
	addi	a5,a5,1
.L86:
	addi	a5,a5,-1
	li	a4,13
	bgtu	a5,a4,.L81
	lui	a4,%hi(lift_levelPos)
	slli	a5,a5,2
	addi	a4,a4,%lo(lift_levelPos)
	add	a5,a4,a5
	lw	a5,0(a5)
	j	.L87
.L85:
	li	a5,4
	bne	a4,a5,.L81
	lui	a5,%hi(lift_level)
	lw	a5,%lo(lift_level)(a5)
	addi	a5,a5,-1
	j	.L86
	.size	lift_wait_for_motor_start, .-lift_wait_for_motor_start
	.section	.text.lift_check_run,"ax",@progbits
	.align	2
	.globl	lift_check_run
	.type	lift_check_run, @function
lift_check_run:
	lui	a5,%hi(lift_cmd)
	lw	a0,%lo(lift_cmd)(a5)
	li	a5,3
	bne	a0,a5,.L89
	lui	a5,%hi(lift_endCnt)
	lw	a5,%lo(lift_endCnt)(a5)
	lui	a4,%hi(lift_cnt)
	lw	a4,%lo(lift_cnt)(a4)
	addi	a5,a5,-1
	ble	a5,a4,.L90
	lui	a5,%hi(lift_ctrl_io_in+4)
	lw	a0,%lo(lift_ctrl_io_in+4)(a5)
.L113:
	seqz	a0,a0
	ret
.L89:
	li	a5,4
	bne	a0,a5,.L92
	lui	a5,%hi(lift_endCnt)
	lw	a5,%lo(lift_endCnt)(a5)
	lui	a4,%hi(lift_cnt)
	lw	a4,%lo(lift_cnt)(a4)
	addi	a5,a5,1
	bge	a5,a4,.L90
	lui	a5,%hi(lift_ctrl_io_in+8)
	lw	a0,%lo(lift_ctrl_io_in+8)(a5)
	j	.L113
.L92:
	li	a5,1
	bne	a0,a5,.L93
	lui	a4,%hi(lift_loadPending)
	lw	a3,%lo(lift_loadPending)(a4)
	lui	a5,%hi(lift_ctrl_io_in)
	addi	a5,a5,%lo(lift_ctrl_io_in)
	beq	a3,zero,.L94
	lw	a3,12(a5)
	beq	a3,zero,.L94
	lui	a5,%hi(lift_level)
	lw	a3,%lo(lift_level)(a5)
	lui	a5,%hi(lift_loadLevel)
	sw	a3,%lo(lift_loadLevel)(a5)
.L112:
	sw	zero,%lo(lift_loadPending)(a4)
.L90:
	li	a0,0
	ret
.L94:
	lw	a5,4(a5)
	bne	a5,zero,.L112
	ret
.L93:
	li	a5,2
	bne	a0,a5,.L90
	lui	a2,%hi(lift_loadPending)
	lw	a4,%lo(lift_loadPending)(a2)
	lui	a5,%hi(lift_ctrl_io_in)
	addi	a5,a5,%lo(lift_ctrl_io_in)
	beq	a4,zero,.L95
	lui	a4,%hi(lift_loadSensor)
	lw	a1,%lo(lift_loadSensor)(a4)
	lw	a3,12(a5)
	beq	a1,zero,.L96
	bne	a3,zero,.L96
	lui	a5,%hi(lift_level)
	sw	zero,%lo(lift_loadSensor)(a4)
	lw	a4,%lo(lift_level)(a5)
	lui	a5,%hi(lift_loadLevel)
	sw	zero,%lo(lift_loadPending)(a2)
	sw	a4,%lo(lift_loadLevel)(a5)
	j	.L90
.L96:
	sw	a3,%lo(lift_loadSensor)(a4)
.L95:
	lw	a0,8(a5)
	j	.L113
	.size	lift_check_run, .-lift_check_run
	.section	.text.lift_do_cmd,"ax",@progbits
	.align	2
	.globl	lift_do_cmd
	.type	lift_do_cmd, @function
lift_do_cmd:
	lui	a5,%hi(lift_timMotor)
	lw	a5,%lo(lift_timMotor)(a5)
	ble	a5,zero,.L115
	tail	lift_wait_for_motor_start
.L115:
	addi	sp,sp,-16
	sw	ra,12(sp)
	call	lift_check_run
	lui	a5,%hi(lift_ctrl_io_out)
	lw	a4,%lo(lift_ctrl_io_out)(a5)
	beq	a4,zero,.L116
	slli	a3,a0,31
	srli	a4,a3,31
	bne	a4,zero,.L116
	lui	a4,%hi(lift_cmd)
	li	a3,99
	sw	a3,%lo(lift_cmd)(a4)
	lui	a4,%hi(lift_timImp)
	li	a3,50
	sw	a3,%lo(lift_timImp)(a4)
.L116:
	lw	ra,12(sp)
	sw	a0,%lo(lift_ctrl_io_out)(a5)
	addi	sp,sp,16
	jr	ra
	.size	lift_do_cmd, .-lift_do_cmd
	.section	.text.lift_ctrl_loop,"ax",@progbits
	.align	2
	.globl	lift_ctrl_loop
	.type	lift_ctrl_loop, @function
lift_ctrl_loop:
	lui	a5,%hi(lift_cmd)
	lw	a5,%lo(lift_cmd)(a5)
	addi	sp,sp,-16
	sw	ra,12(sp)
	bne	a5,zero,.L126
	call	lift_check_cmd
.L127:
	call	lift_check_level
	lui	a3,%hi(lift_dbgCnt)
	lw	a5,%lo(lift_dbgCnt)(a3)
	lw	ra,12(sp)
	lui	a2,%hi(lift_ctrl_io_led+52)
	srli	a4,a5,7
	andi	a4,a4,1
	addi	a5,a5,1
	sw	a4,%lo(lift_ctrl_io_led+52)(a2)
	sw	a5,%lo(lift_dbgCnt)(a3)
	addi	sp,sp,16
	jr	ra
.L126:
	lui	a5,%hi(lift_ctrl_io_in)
	addi	a5,a5,%lo(lift_ctrl_io_in)
	lui	a4,%hi(lift_ctrl_io_out)
	lw	a2,8(a5)
	lw	a1,%lo(lift_ctrl_io_out)(a4)
	lw	a0,0(a5)
	call	lift_do_impulse
	call	lift_do_cmd
	j	.L127
	.size	lift_ctrl_loop, .-lift_ctrl_loop
	.section	.text.lift_controller,"ax",@progbits
	.align	2
	.globl	lift_controller
	.type	lift_controller, @function
lift_controller:
	addi	sp,sp,-16
	sw	ra,12(sp)
	call	lift_ctrl_get_vals
	call	lift_ctrl_loop
	lw	ra,12(sp)
	addi	sp,sp,16
	tail	lift_ctrl_set_vals
	.size	lift_controller, .-lift_controller
	.section	.text.lift_main,"ax",@progbits
	.align	2
	.globl	lift_main
	.type	lift_main, @function
lift_main:
	addi	sp,sp,-32
	sw	s0,24(sp)
	sw	s1,20(sp)
	sw	s2,16(sp)
	sw	s3,12(sp)
	sw	s4,8(sp)
	sw	ra,28(sp)
	li	s0,1001
	lui	s4,%hi(lift_simio_in)
	lui	s3,%hi(lift_simio_adc1)
	lui	s2,%hi(lift_simio_adc2)
	lui	s1,%hi(lift_simio_adc3)
.L132:
	sw	zero,%lo(lift_simio_in)(s4)
	sw	zero,%lo(lift_simio_adc1)(s3)
	sw	zero,%lo(lift_simio_adc2)(s2)
	addi	s0,s0,-1
	sw	zero,%lo(lift_simio_adc3)(s1)
	call	lift_controller
	bne	s0,zero,.L132
	lw	ra,28(sp)
	lw	s0,24(sp)
	lw	s1,20(sp)
	lw	s2,16(sp)
	lw	s3,12(sp)
	lw	s4,8(sp)
	addi	sp,sp,32
	jr	ra
	.size	lift_main, .-lift_main
	.section	.text.isaforge_tacle_lift_original_main,"ax",@progbits
	.align	2
	.globl	isaforge_tacle_lift_original_main
	.type	isaforge_tacle_lift_original_main, @function
isaforge_tacle_lift_original_main:
	addi	sp,sp,-16
	sw	ra,12(sp)
	call	lift_init
	call	lift_main
	lui	a5,%hi(lift_checksum)
	lw	a0,%lo(lift_checksum)(a5)
	lw	ra,12(sp)
	li	a5,-4005888
	add	a0,a0,a5
	snez	a0,a0
	addi	sp,sp,16
	jr	ra
	.size	isaforge_tacle_lift_original_main, .-isaforge_tacle_lift_original_main
	.section	.text.initialise_benchmark,"ax",@progbits
	.align	2
	.globl	initialise_benchmark
	.type	initialise_benchmark, @function
initialise_benchmark:
	tail	lift_init
	.size	initialise_benchmark, .-initialise_benchmark
	.section	.text.warm_caches,"ax",@progbits
	.align	2
	.globl	warm_caches
	.type	warm_caches, @function
warm_caches:
	ret
	.size	warm_caches, .-warm_caches
	.section	.text.benchmark,"ax",@progbits
	.align	2
	.globl	benchmark
	.type	benchmark, @function
benchmark:
	addi	sp,sp,-16
	sw	ra,12(sp)
	call	lift_main
	lui	a5,%hi(lift_checksum)
	lw	a0,%lo(lift_checksum)(a5)
	lw	ra,12(sp)
	li	a5,-4005888
	add	a0,a0,a5
	snez	a0,a0
	addi	sp,sp,16
	jr	ra
	.size	benchmark, .-benchmark
	.section	.text.verify_benchmark,"ax",@progbits
	.align	2
	.globl	verify_benchmark
	.type	verify_benchmark, @function
verify_benchmark:
	bne	a0,zero,.L143
	lui	a5,%hi(lift_checksum)
	lw	a0,%lo(lift_checksum)(a5)
	li	a5,-4005888
	add	a0,a0,a5
	seqz	a0,a0
	ret
.L143:
	li	a0,0
	ret
	.size	verify_benchmark, .-verify_benchmark
	.globl	lift_endCnt
	.section	.bss.lift_endCnt,"aw",@nobits
	.align	2
	.type	lift_endCnt, @object
	.size	lift_endCnt, 4
lift_endCnt:
	.zero	4
	.globl	lift_dbgCnt
	.section	.bss.lift_dbgCnt,"aw",@nobits
	.align	2
	.type	lift_dbgCnt, @object
	.size	lift_dbgCnt, 4
lift_dbgCnt:
	.zero	4
	.globl	lift_lastImp
	.section	.bss.lift_lastImp,"aw",@nobits
	.align	2
	.type	lift_lastImp, @object
	.size	lift_lastImp, 4
lift_lastImp:
	.zero	4
	.globl	lift_directionUp
	.section	.bss.lift_directionUp,"aw",@nobits
	.align	2
	.type	lift_directionUp, @object
	.size	lift_directionUp, 4
lift_directionUp:
	.zero	4
	.globl	lift_timImp
	.section	.bss.lift_timImp,"aw",@nobits
	.align	2
	.type	lift_timImp, @object
	.size	lift_timImp, 4
lift_timImp:
	.zero	4
	.globl	lift_timMotor
	.section	.bss.lift_timMotor,"aw",@nobits
	.align	2
	.type	lift_timMotor, @object
	.size	lift_timMotor, 4
lift_timMotor:
	.zero	4
	.globl	lift_cmd
	.section	.bss.lift_cmd,"aw",@nobits
	.align	2
	.type	lift_cmd, @object
	.size	lift_cmd, 4
lift_cmd:
	.zero	4
	.globl	lift_loadSensor
	.section	.bss.lift_loadSensor,"aw",@nobits
	.align	2
	.type	lift_loadSensor, @object
	.size	lift_loadSensor, 4
lift_loadSensor:
	.zero	4
	.globl	lift_loadPending
	.section	.bss.lift_loadPending,"aw",@nobits
	.align	2
	.type	lift_loadPending, @object
	.size	lift_loadPending, 4
lift_loadPending:
	.zero	4
	.globl	lift_loadLevel
	.section	.bss.lift_loadLevel,"aw",@nobits
	.align	2
	.type	lift_loadLevel, @object
	.size	lift_loadLevel, 4
lift_loadLevel:
	.zero	4
	.globl	lift_level
	.section	.bss.lift_level,"aw",@nobits
	.align	2
	.type	lift_level, @object
	.size	lift_level, 4
lift_level:
	.zero	4
	.globl	lift_cnt
	.section	.bss.lift_cnt,"aw",@nobits
	.align	2
	.type	lift_cnt, @object
	.size	lift_cnt, 4
lift_cnt:
	.zero	4
	.globl	lift_cntValid
	.section	.bss.lift_cntValid,"aw",@nobits
	.align	2
	.type	lift_cntValid, @object
	.size	lift_cntValid, 4
lift_cntValid:
	.zero	4
	.globl	lift_one_level
	.section	.bss.lift_one_level,"aw",@nobits
	.align	2
	.type	lift_one_level, @object
	.size	lift_one_level, 4
lift_one_level:
	.zero	4
	.globl	lift_levelPos
	.section	.bss.lift_levelPos,"aw",@nobits
	.align	2
	.type	lift_levelPos, @object
	.size	lift_levelPos, 64
lift_levelPos:
	.zero	64
	.globl	lift_simio_adc3
	.section	.bss.lift_simio_adc3,"aw",@nobits
	.align	2
	.type	lift_simio_adc3, @object
	.size	lift_simio_adc3, 4
lift_simio_adc3:
	.zero	4
	.globl	lift_simio_adc2
	.section	.bss.lift_simio_adc2,"aw",@nobits
	.align	2
	.type	lift_simio_adc2, @object
	.size	lift_simio_adc2, 4
lift_simio_adc2:
	.zero	4
	.globl	lift_simio_adc1
	.section	.bss.lift_simio_adc1,"aw",@nobits
	.align	2
	.type	lift_simio_adc1, @object
	.size	lift_simio_adc1, 4
lift_simio_adc1:
	.zero	4
	.globl	lift_simio_led
	.section	.bss.lift_simio_led,"aw",@nobits
	.align	2
	.type	lift_simio_led, @object
	.size	lift_simio_led, 4
lift_simio_led:
	.zero	4
	.globl	lift_simio_out
	.section	.bss.lift_simio_out,"aw",@nobits
	.align	2
	.type	lift_simio_out, @object
	.size	lift_simio_out, 4
lift_simio_out:
	.zero	4
	.globl	lift_simio_in
	.section	.bss.lift_simio_in,"aw",@nobits
	.align	2
	.type	lift_simio_in, @object
	.size	lift_simio_in, 4
lift_simio_in:
	.zero	4
	.globl	lift_ctrl_dly2
	.section	.bss.lift_ctrl_dly2,"aw",@nobits
	.align	2
	.type	lift_ctrl_dly2, @object
	.size	lift_ctrl_dly2, 4
lift_ctrl_dly2:
	.zero	4
	.globl	lift_ctrl_dly1
	.section	.bss.lift_ctrl_dly1,"aw",@nobits
	.align	2
	.type	lift_ctrl_dly1, @object
	.size	lift_ctrl_dly1, 4
lift_ctrl_dly1:
	.zero	4
	.globl	lift_ctrl_io_led
	.section	.bss.lift_ctrl_io_led,"aw",@nobits
	.align	2
	.type	lift_ctrl_io_led, @object
	.size	lift_ctrl_io_led, 64
lift_ctrl_io_led:
	.zero	64
	.globl	lift_ctrl_io_analog
	.section	.bss.lift_ctrl_io_analog,"aw",@nobits
	.align	2
	.type	lift_ctrl_io_analog, @object
	.size	lift_ctrl_io_analog, 16
lift_ctrl_io_analog:
	.zero	16
	.globl	lift_ctrl_io_out
	.section	.bss.lift_ctrl_io_out,"aw",@nobits
	.align	2
	.type	lift_ctrl_io_out, @object
	.size	lift_ctrl_io_out, 16
lift_ctrl_io_out:
	.zero	16
	.globl	lift_ctrl_io_in
	.section	.bss.lift_ctrl_io_in,"aw",@nobits
	.align	2
	.type	lift_ctrl_io_in, @object
	.size	lift_ctrl_io_in, 40
lift_ctrl_io_in:
	.zero	40
	.globl	lift_checksum
	.section	.bss.lift_checksum,"aw",@nobits
	.align	2
	.type	lift_checksum, @object
	.size	lift_checksum, 4
lift_checksum:
	.zero	4
	.ident	"GCC: (xPack GNU RISC-V Embedded GCC arm64) 15.2.0"
	.section	.note.GNU-stack,"",@progbits
