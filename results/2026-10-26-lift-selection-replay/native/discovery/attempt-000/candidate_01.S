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
__isaforge_begin_0:
	lui	a5,%hi(lift_checksum)
__isaforge_end_0:
__isaforge_begin_1:
	lw	a0,%lo(lift_checksum)(a5)
__isaforge_end_1:
__isaforge_begin_2:
	li	a5,-4005888
__isaforge_end_2:
__isaforge_begin_3:
	add	a0,a0,a5
__isaforge_end_3:
__isaforge_begin_4:
	snez	a0,a0
__isaforge_end_4:
__isaforge_begin_5:
	ret
__isaforge_end_5:
	.size	lift_return, .-lift_return
	.section	.text.lift_io_init,"ax",@progbits
	.align	2
	.globl	lift_io_init
	.type	lift_io_init, @function
lift_io_init:
__isaforge_begin_6:
	lui	a5,%hi(lift_ctrl_dly1)
__isaforge_end_6:
__isaforge_begin_7:
	sw	zero,%lo(lift_ctrl_dly1)(a5)
__isaforge_end_7:
__isaforge_begin_8:
	lui	a5,%hi(lift_ctrl_dly2)
__isaforge_end_8:
__isaforge_begin_9:
	sw	zero,%lo(lift_ctrl_dly2)(a5)
__isaforge_end_9:
__isaforge_begin_10:
	ret
__isaforge_end_10:
	.size	lift_io_init, .-lift_io_init
	.section	.text.lift_ctrl_set_vals,"ax",@progbits
	.align	2
	.globl	lift_ctrl_set_vals
	.type	lift_ctrl_set_vals, @function
lift_ctrl_set_vals:
__isaforge_begin_11:
	lui	a4,%hi(lift_ctrl_io_out)
__isaforge_end_11:
__isaforge_begin_12:
	addi	a4,a4,%lo(lift_ctrl_io_out)
__isaforge_end_12:
__isaforge_begin_13:
	addi	a2,a4,-16
__isaforge_end_13:
__isaforge_begin_14:
	li	a5,0
__isaforge_end_14:
.L4:
__isaforge_begin_15:
	lw	a3,12(a4)
__isaforge_end_15:
__isaforge_begin_16:
	slli	a5,a5,1
__isaforge_end_16:
__isaforge_begin_17:
	addi	a4,a4,-4
__isaforge_end_17:
__isaforge_begin_18:
	snez	a3,a3
__isaforge_end_18:
__isaforge_begin_19:
	or	a5,a3,a5
__isaforge_end_19:
__isaforge_begin_20:
	bne	a2,a4,.L4
__isaforge_end_20:
__isaforge_begin_21:
	lui	a4,%hi(lift_simio_out)
__isaforge_end_21:
__isaforge_begin_22:
	sw	a5,%lo(lift_simio_out)(a4)
__isaforge_end_22:
__isaforge_begin_23:
	lui	a4,%hi(lift_ctrl_io_led)
__isaforge_end_23:
__isaforge_begin_24:
	addi	a4,a4,%lo(lift_ctrl_io_led)
__isaforge_end_24:
__isaforge_begin_25:
	addi	a2,a4,-56
__isaforge_end_25:
.L5:
__isaforge_begin_26:
	lw	a3,52(a4)
__isaforge_end_26:
__isaforge_begin_27:
	slli	a5,a5,1
__isaforge_end_27:
__isaforge_begin_28:
	addi	a4,a4,-4
__isaforge_end_28:
__isaforge_begin_29:
	snez	a3,a3
__isaforge_end_29:
__isaforge_begin_30:
	or	a5,a3,a5
__isaforge_end_30:
__isaforge_begin_31:
	bne	a2,a4,.L5
__isaforge_end_31:
__isaforge_begin_32:
	lui	a4,%hi(lift_simio_led)
__isaforge_end_32:
__isaforge_begin_33:
	lui	a3,%hi(lift_checksum)
__isaforge_end_33:
__isaforge_begin_34:
	sw	a5,%lo(lift_simio_led)(a4)
__isaforge_end_34:
__isaforge_begin_35:
	lw	a4,%lo(lift_checksum)(a3)
__isaforge_end_35:
__isaforge_begin_36:
	add	a5,a4,a5
__isaforge_end_36:
__isaforge_begin_37:
	sw	a5,%lo(lift_checksum)(a3)
__isaforge_end_37:
__isaforge_begin_38:
	ret
__isaforge_end_38:
	.size	lift_ctrl_set_vals, .-lift_ctrl_set_vals
	.section	.text.lift_ctrl_get_vals,"ax",@progbits
	.align	2
	.globl	lift_ctrl_get_vals
	.type	lift_ctrl_get_vals, @function
lift_ctrl_get_vals:
__isaforge_begin_39:
	lui	a5,%hi(lift_simio_in)
__isaforge_end_39:
__isaforge_begin_40:
	lw	a3,%lo(lift_simio_in)(a5)
__isaforge_end_40:
__isaforge_begin_41:
	lui	a5,%hi(lift_ctrl_dly1)
__isaforge_end_41:
__isaforge_begin_42:
	lw	a0,%lo(lift_ctrl_dly1)(a5)
__isaforge_end_42:
__isaforge_begin_43:
	lui	a4,%hi(lift_ctrl_dly2)
__isaforge_end_43:
__isaforge_begin_44:
	lhu	a2,%lo(lift_ctrl_dly2)(a4)
__isaforge_end_44:
__isaforge_begin_45:
	slli	a3,a3,16
__isaforge_end_45:
__isaforge_begin_46:
	sw	a0,%lo(lift_ctrl_dly2)(a4)
__isaforge_end_46:
__isaforge_begin_47:
	lui	a4,%hi(lift_ctrl_io_in)
__isaforge_end_47:
__isaforge_begin_48:
	slli	a1,a0,16
__isaforge_end_48:
__isaforge_begin_49:
	srli	a3,a3,16
__isaforge_end_49:
__isaforge_begin_50:
	addi	a4,a4,%lo(lift_ctrl_io_in)
__isaforge_end_50:
__isaforge_begin_51:
	srli	a1,a1,16
__isaforge_end_51:
__isaforge_begin_52:
	sw	a3,%lo(lift_ctrl_dly1)(a5)
__isaforge_end_52:
__isaforge_begin_53:
	addi	a0,a4,40
__isaforge_end_53:
.L9:
__isaforge_begin_54:
__isaforge_end_54:
__isaforge_begin_55:
__isaforge_end_55:
__isaforge_begin_56:
	.insn r 0x0b, 0, 1, x15, x13, x11
__isaforge_end_56:
__isaforge_begin_57:
	andi	a6,a2,1
__isaforge_end_57:
__isaforge_begin_58:
	add	a5,a5,a6
__isaforge_end_58:
__isaforge_begin_59:
	slti	a5,a5,2
__isaforge_end_59:
__isaforge_begin_60:
	seqz	a5,a5
__isaforge_end_60:
__isaforge_begin_61:
	sw	a5,0(a4)
__isaforge_end_61:
__isaforge_begin_62:
	addi	a4,a4,4
__isaforge_end_62:
__isaforge_begin_63:
	srli	a3,a3,1
__isaforge_end_63:
__isaforge_begin_64:
	srli	a1,a1,1
__isaforge_end_64:
__isaforge_begin_65:
	srli	a2,a2,1
__isaforge_end_65:
__isaforge_begin_66:
	bne	a0,a4,.L9
__isaforge_end_66:
__isaforge_begin_67:
	lui	a5,%hi(lift_simio_adc1)
__isaforge_end_67:
__isaforge_begin_68:
	lw	a4,%lo(lift_simio_adc1)(a5)
__isaforge_end_68:
__isaforge_begin_69:
	lui	a5,%hi(lift_ctrl_io_analog)
__isaforge_end_69:
__isaforge_begin_70:
	addi	a5,a5,%lo(lift_ctrl_io_analog)
__isaforge_end_70:
__isaforge_begin_71:
	sw	a4,0(a5)
__isaforge_end_71:
__isaforge_begin_72:
	lui	a4,%hi(lift_simio_adc2)
__isaforge_end_72:
__isaforge_begin_73:
	lw	a4,%lo(lift_simio_adc2)(a4)
__isaforge_end_73:
__isaforge_begin_74:
	sw	a4,4(a5)
__isaforge_end_74:
__isaforge_begin_75:
	lui	a4,%hi(lift_simio_adc3)
__isaforge_end_75:
__isaforge_begin_76:
	lw	a4,%lo(lift_simio_adc3)(a4)
__isaforge_end_76:
__isaforge_begin_77:
	sw	a4,8(a5)
__isaforge_end_77:
__isaforge_begin_78:
	ret
__isaforge_end_78:
	.size	lift_ctrl_get_vals, .-lift_ctrl_get_vals
	.section	.text.lift_ctrl_init,"ax",@progbits
	.align	2
	.globl	lift_ctrl_init
	.type	lift_ctrl_init, @function
lift_ctrl_init:
__isaforge_begin_79:
	addi	sp,sp,-16
__isaforge_end_79:
__isaforge_begin_80:
	lui	a5,%hi(lift_checksum)
__isaforge_end_80:
__isaforge_begin_81:
	sw	ra,12(sp)
__isaforge_end_81:
__isaforge_begin_82:
	sw	zero,%lo(lift_checksum)(a5)
__isaforge_end_82:
__isaforge_begin_83:
	call	lift_io_init
__isaforge_end_83:
__isaforge_begin_84:
	lui	a5,%hi(lift_cntValid)
__isaforge_end_84:
__isaforge_begin_85:
	sw	zero,%lo(lift_cntValid)(a5)
__isaforge_end_85:
__isaforge_begin_86:
	lui	a5,%hi(lift_cnt)
__isaforge_end_86:
__isaforge_begin_87:
	sw	zero,%lo(lift_cnt)(a5)
__isaforge_end_87:
__isaforge_begin_88:
	lui	a5,%hi(lift_cmd)
__isaforge_end_88:
__isaforge_begin_89:
	sw	zero,%lo(lift_cmd)(a5)
__isaforge_end_89:
__isaforge_begin_90:
	lui	a5,%hi(lift_timMotor)
__isaforge_end_90:
__isaforge_begin_91:
	sw	zero,%lo(lift_timMotor)(a5)
__isaforge_end_91:
__isaforge_begin_92:
	lui	a5,%hi(lift_timImp)
__isaforge_end_92:
__isaforge_begin_93:
	sw	zero,%lo(lift_timImp)(a5)
__isaforge_end_93:
__isaforge_begin_94:
	li	a4,1
__isaforge_end_94:
__isaforge_begin_95:
	lui	a5,%hi(lift_directionUp)
__isaforge_end_95:
__isaforge_begin_96:
	sw	a4,%lo(lift_directionUp)(a5)
__isaforge_end_96:
__isaforge_begin_97:
	lui	a5,%hi(lift_lastImp)
__isaforge_end_97:
__isaforge_begin_98:
	sw	zero,%lo(lift_lastImp)(a5)
__isaforge_end_98:
__isaforge_begin_99:
	lui	a5,%hi(lift_loadLevel)
__isaforge_end_99:
__isaforge_begin_100:
	sw	zero,%lo(lift_loadLevel)(a5)
__isaforge_end_100:
__isaforge_begin_101:
	lui	a5,%hi(lift_loadPending)
__isaforge_end_101:
__isaforge_begin_102:
	sw	zero,%lo(lift_loadPending)(a5)
__isaforge_end_102:
__isaforge_begin_103:
	lui	a5,%hi(lift_loadSensor)
__isaforge_end_103:
__isaforge_begin_104:
	sw	zero,%lo(lift_loadSensor)(a5)
__isaforge_end_104:
__isaforge_begin_105:
	lui	a5,%hi(lift_levelPos)
__isaforge_end_105:
__isaforge_begin_106:
	addi	a5,a5,%lo(lift_levelPos)
__isaforge_end_106:
__isaforge_begin_107:
	li	a3,115
__isaforge_end_107:
__isaforge_begin_108:
	sw	a3,8(a5)
__isaforge_end_108:
__isaforge_begin_109:
	li	a3,173
__isaforge_end_109:
__isaforge_begin_110:
	sw	a3,12(a5)
__isaforge_end_110:
__isaforge_begin_111:
	li	a3,230
__isaforge_end_111:
__isaforge_begin_112:
	sw	a3,16(a5)
__isaforge_end_112:
__isaforge_begin_113:
	li	a3,288
__isaforge_end_113:
__isaforge_begin_114:
	sw	a3,20(a5)
__isaforge_end_114:
__isaforge_begin_115:
	li	a3,346
__isaforge_end_115:
__isaforge_begin_116:
	sw	a3,24(a5)
__isaforge_end_116:
__isaforge_begin_117:
	li	a3,403
__isaforge_end_117:
__isaforge_begin_118:
	sw	a3,28(a5)
__isaforge_end_118:
__isaforge_begin_119:
	li	a3,461
__isaforge_end_119:
__isaforge_begin_120:
	sw	a3,32(a5)
__isaforge_end_120:
__isaforge_begin_121:
	li	a3,518
__isaforge_end_121:
__isaforge_begin_122:
	sw	a3,36(a5)
__isaforge_end_122:
__isaforge_begin_123:
	li	a3,576
__isaforge_end_123:
__isaforge_begin_124:
	sw	a3,40(a5)
__isaforge_end_124:
__isaforge_begin_125:
	li	a3,634
__isaforge_end_125:
__isaforge_begin_126:
	sw	a3,44(a5)
__isaforge_end_126:
__isaforge_begin_127:
	li	a3,691
__isaforge_end_127:
__isaforge_begin_128:
	sw	a3,48(a5)
__isaforge_end_128:
__isaforge_begin_129:
	li	a3,749
__isaforge_end_129:
__isaforge_begin_130:
	sw	a3,52(a5)
__isaforge_end_130:
__isaforge_begin_131:
	li	a3,806
__isaforge_end_131:
__isaforge_begin_132:
	sw	a3,56(a5)
__isaforge_end_132:
__isaforge_begin_133:
	lw	ra,12(sp)
__isaforge_end_133:
__isaforge_begin_134:
	li	a4,58
__isaforge_end_134:
__isaforge_begin_135:
	li	a3,864
__isaforge_end_135:
__isaforge_begin_136:
	sw	zero,0(a5)
__isaforge_end_136:
__isaforge_begin_137:
	sw	a4,4(a5)
__isaforge_end_137:
__isaforge_begin_138:
	sw	a3,60(a5)
__isaforge_end_138:
__isaforge_begin_139:
	lui	a5,%hi(lift_one_level)
__isaforge_end_139:
__isaforge_begin_140:
	sw	a4,%lo(lift_one_level)(a5)
__isaforge_end_140:
__isaforge_begin_141:
	addi	sp,sp,16
__isaforge_end_141:
__isaforge_begin_142:
	jr	ra
__isaforge_end_142:
	.size	lift_ctrl_init, .-lift_ctrl_init
	.section	.text.lift_init,"ax",@progbits
	.align	2
	.globl	lift_init
	.type	lift_init, @function
lift_init:
__isaforge_begin_143:
	addi	sp,sp,-16
__isaforge_end_143:
__isaforge_begin_144:
	lui	a5,%hi(lift_ctrl_io_in)
__isaforge_end_144:
__isaforge_begin_145:
	lui	a4,%hi(lift_ctrl_io_in+40)
__isaforge_end_145:
__isaforge_begin_146:
	sb	zero,15(sp)
__isaforge_end_146:
__isaforge_begin_147:
	addi	a5,a5,%lo(lift_ctrl_io_in)
__isaforge_end_147:
__isaforge_begin_148:
	addi	a4,a4,%lo(lift_ctrl_io_in+40)
__isaforge_end_148:
.L14:
__isaforge_begin_149:
	lbu	a2,0(a5)
__isaforge_end_149:
__isaforge_begin_150:
	lbu	a3,15(sp)
__isaforge_end_150:
__isaforge_begin_151:
	addi	a5,a5,1
__isaforge_end_151:
__isaforge_begin_152:
	xor	a3,a3,a2
__isaforge_end_152:
__isaforge_begin_153:
	sb	a3,-1(a5)
__isaforge_end_153:
__isaforge_begin_154:
	bne	a5,a4,.L14
__isaforge_end_154:
__isaforge_begin_155:
	lui	a5,%hi(lift_ctrl_io_out)
__isaforge_end_155:
__isaforge_begin_156:
	lui	a4,%hi(lift_ctrl_io_out+16)
__isaforge_end_156:
__isaforge_begin_157:
	addi	a5,a5,%lo(lift_ctrl_io_out)
__isaforge_end_157:
__isaforge_begin_158:
	addi	a4,a4,%lo(lift_ctrl_io_out+16)
__isaforge_end_158:
.L15:
__isaforge_begin_159:
	lbu	a2,0(a5)
__isaforge_end_159:
__isaforge_begin_160:
	lbu	a3,15(sp)
__isaforge_end_160:
__isaforge_begin_161:
	addi	a5,a5,1
__isaforge_end_161:
__isaforge_begin_162:
	xor	a3,a3,a2
__isaforge_end_162:
__isaforge_begin_163:
	sb	a3,-1(a5)
__isaforge_end_163:
__isaforge_begin_164:
	bne	a5,a4,.L15
__isaforge_end_164:
__isaforge_begin_165:
	lui	a5,%hi(lift_ctrl_io_analog)
__isaforge_end_165:
__isaforge_begin_166:
	lui	a4,%hi(lift_ctrl_io_analog+16)
__isaforge_end_166:
__isaforge_begin_167:
	addi	a5,a5,%lo(lift_ctrl_io_analog)
__isaforge_end_167:
__isaforge_begin_168:
	addi	a4,a4,%lo(lift_ctrl_io_analog+16)
__isaforge_end_168:
.L16:
__isaforge_begin_169:
	lbu	a2,0(a5)
__isaforge_end_169:
__isaforge_begin_170:
	lbu	a3,15(sp)
__isaforge_end_170:
__isaforge_begin_171:
	addi	a5,a5,1
__isaforge_end_171:
__isaforge_begin_172:
	xor	a3,a3,a2
__isaforge_end_172:
__isaforge_begin_173:
	sb	a3,-1(a5)
__isaforge_end_173:
__isaforge_begin_174:
	bne	a5,a4,.L16
__isaforge_end_174:
__isaforge_begin_175:
	lui	a5,%hi(lift_ctrl_io_led)
__isaforge_end_175:
__isaforge_begin_176:
	lui	a4,%hi(lift_ctrl_io_led+64)
__isaforge_end_176:
__isaforge_begin_177:
	addi	a5,a5,%lo(lift_ctrl_io_led)
__isaforge_end_177:
__isaforge_begin_178:
	addi	a4,a4,%lo(lift_ctrl_io_led+64)
__isaforge_end_178:
.L17:
__isaforge_begin_179:
	lbu	a2,0(a5)
__isaforge_end_179:
__isaforge_begin_180:
	lbu	a3,15(sp)
__isaforge_end_180:
__isaforge_begin_181:
	addi	a5,a5,1
__isaforge_end_181:
__isaforge_begin_182:
	xor	a3,a3,a2
__isaforge_end_182:
__isaforge_begin_183:
	sb	a3,-1(a5)
__isaforge_end_183:
__isaforge_begin_184:
	bne	a5,a4,.L17
__isaforge_end_184:
__isaforge_begin_185:
	lui	a5,%hi(lift_checksum)
__isaforge_end_185:
__isaforge_begin_186:
	sw	zero,%lo(lift_checksum)(a5)
__isaforge_end_186:
__isaforge_begin_187:
	addi	sp,sp,16
__isaforge_end_187:
__isaforge_begin_188:
	tail	lift_ctrl_init
__isaforge_end_188:
	.size	lift_init, .-lift_init
	.section	.text.lift_check_level,"ax",@progbits
	.align	2
	.globl	lift_check_level
	.type	lift_check_level, @function
lift_check_level:
__isaforge_begin_189:
	lui	a5,%hi(lift_cntValid)
__isaforge_end_189:
__isaforge_begin_190:
	lw	a5,%lo(lift_cntValid)(a5)
__isaforge_end_190:
__isaforge_begin_191:
	lui	a4,%hi(lift_level)
__isaforge_end_191:
__isaforge_begin_192:
	beq	a5,zero,.L24
__isaforge_end_192:
__isaforge_begin_193:
	lui	a5,%hi(lift_one_level)
__isaforge_end_193:
__isaforge_begin_194:
	lw	a1,%lo(lift_one_level)(a5)
__isaforge_end_194:
__isaforge_begin_195:
	lui	a3,%hi(lift_cnt)
__isaforge_end_195:
__isaforge_begin_196:
	lw	a7,%lo(lift_cnt)(a3)
__isaforge_end_196:
__isaforge_begin_197:
	li	a5,1
__isaforge_end_197:
__isaforge_begin_198:
	lui	a3,%hi(lift_levelPos)
__isaforge_end_198:
__isaforge_begin_199:
	srai	a1,a1,2
__isaforge_end_199:
__isaforge_begin_200:
	sw	a5,%lo(lift_level)(a4)
__isaforge_end_200:
__isaforge_begin_201:
	addi	a3,a3,%lo(lift_levelPos)
__isaforge_end_201:
__isaforge_begin_202:
	li	a2,0
__isaforge_end_202:
__isaforge_begin_203:
	li	a6,14
__isaforge_end_203:
.L25:
__isaforge_begin_204:
	beq	a5,a6,.L38
__isaforge_end_204:
__isaforge_begin_205:
	lw	a0,4(a3)
__isaforge_end_205:
__isaforge_begin_206:
	addi	a3,a3,4
__isaforge_end_206:
__isaforge_begin_207:
	sub	a0,a0,a1
__isaforge_end_207:
__isaforge_begin_208:
	ble	a0,a7,.L29
__isaforge_end_208:
.L38:
__isaforge_begin_209:
	beq	a2,zero,.L26
__isaforge_end_209:
__isaforge_begin_210:
	sw	a5,%lo(lift_level)(a4)
__isaforge_end_210:
.L26:
__isaforge_begin_211:
	lw	a2,%lo(lift_level)(a4)
__isaforge_end_211:
__isaforge_begin_212:
	lui	a5,%hi(lift_ctrl_io_led)
__isaforge_end_212:
__isaforge_begin_213:
	addi	a5,a5,%lo(lift_ctrl_io_led)
__isaforge_end_213:
__isaforge_begin_214:
	addi	a2,a2,-1
__isaforge_end_214:
__isaforge_begin_215:
	li	a4,0
__isaforge_end_215:
__isaforge_begin_216:
	li	a1,14
__isaforge_end_216:
.L28:
__isaforge_begin_217:
	sub	a3,a2,a4
__isaforge_end_217:
__isaforge_begin_218:
	seqz	a3,a3
__isaforge_end_218:
__isaforge_begin_219:
	sw	a3,0(a5)
__isaforge_end_219:
__isaforge_begin_220:
	addi	a4,a4,1
__isaforge_end_220:
__isaforge_begin_221:
	addi	a5,a5,4
__isaforge_end_221:
__isaforge_begin_222:
	bne	a4,a1,.L28
__isaforge_end_222:
__isaforge_begin_223:
	ret
__isaforge_end_223:
.L29:
__isaforge_begin_224:
	addi	a5,a5,1
__isaforge_end_224:
__isaforge_begin_225:
	li	a2,1
__isaforge_end_225:
__isaforge_begin_226:
	j	.L25
__isaforge_end_226:
.L24:
__isaforge_begin_227:
	sw	zero,%lo(lift_level)(a4)
__isaforge_end_227:
__isaforge_begin_228:
	j	.L26
__isaforge_end_228:
	.size	lift_check_level, .-lift_check_level
	.section	.text.lift_check_cmd,"ax",@progbits
	.align	2
	.globl	lift_check_cmd
	.type	lift_check_cmd, @function
lift_check_cmd:
__isaforge_begin_229:
	lui	a3,%hi(lift_loadPending)
__isaforge_end_229:
__isaforge_begin_230:
	lw	a2,%lo(lift_loadPending)(a3)
__isaforge_end_230:
__isaforge_begin_231:
	lui	a5,%hi(lift_ctrl_io_in)
__isaforge_end_231:
__isaforge_begin_232:
	addi	a5,a5,%lo(lift_ctrl_io_in)
__isaforge_end_232:
__isaforge_begin_233:
	lui	a4,%hi(lift_cmd)
__isaforge_end_233:
__isaforge_begin_234:
	beq	a2,zero,.L40
__isaforge_end_234:
__isaforge_begin_235:
	lw	a5,8(a5)
__isaforge_end_235:
__isaforge_begin_236:
	beq	a5,zero,.L41
__isaforge_end_236:
.L48:
__isaforge_begin_237:
	li	a5,1
__isaforge_end_237:
.L62:
__isaforge_begin_238:
	sw	a5,%lo(lift_cmd)(a4)
__isaforge_end_238:
.L42:
__isaforge_begin_239:
	lui	a5,%hi(lift_timMotor)
__isaforge_end_239:
__isaforge_begin_240:
	li	a4,50
__isaforge_end_240:
__isaforge_begin_241:
	sw	a4,%lo(lift_timMotor)(a5)
__isaforge_end_241:
__isaforge_begin_242:
	ret
__isaforge_end_242:
.L40:
__isaforge_begin_243:
	lw	a2,16(a5)
__isaforge_end_243:
__isaforge_begin_244:
	beq	a2,zero,.L43
__isaforge_end_244:
__isaforge_begin_245:
	lw	a5,4(a5)
__isaforge_end_245:
__isaforge_begin_246:
	bne	a5,zero,.L41
__isaforge_end_246:
__isaforge_begin_247:
	lui	a5,%hi(lift_level)
__isaforge_end_247:
__isaforge_begin_248:
	lw	a3,%lo(lift_level)(a5)
__isaforge_end_248:
__isaforge_begin_249:
	li	a5,14
__isaforge_end_249:
__isaforge_begin_250:
	beq	a3,a5,.L41
__isaforge_end_250:
__isaforge_begin_251:
	li	a5,3
__isaforge_end_251:
__isaforge_begin_252:
	j	.L62
__isaforge_end_252:
.L43:
__isaforge_begin_253:
	lw	a2,20(a5)
__isaforge_end_253:
__isaforge_begin_254:
	beq	a2,zero,.L44
__isaforge_end_254:
__isaforge_begin_255:
	lw	a5,8(a5)
__isaforge_end_255:
__isaforge_begin_256:
	bne	a5,zero,.L41
__isaforge_end_256:
__isaforge_begin_257:
	lui	a5,%hi(lift_level)
__isaforge_end_257:
__isaforge_begin_258:
	lw	a3,%lo(lift_level)(a5)
__isaforge_end_258:
__isaforge_begin_259:
	li	a5,1
__isaforge_end_259:
__isaforge_begin_260:
	beq	a3,a5,.L41
__isaforge_end_260:
__isaforge_begin_261:
	li	a5,4
__isaforge_end_261:
__isaforge_begin_262:
	j	.L62
__isaforge_end_262:
.L44:
__isaforge_begin_263:
	lw	a2,32(a5)
__isaforge_end_263:
__isaforge_begin_264:
	beq	a2,zero,.L45
__isaforge_end_264:
__isaforge_begin_265:
	lui	a5,%hi(lift_loadLevel)
__isaforge_end_265:
__isaforge_begin_266:
	lw	a5,%lo(lift_loadLevel)(a5)
__isaforge_end_266:
__isaforge_begin_267:
	li	a2,2
__isaforge_end_267:
__isaforge_begin_268:
	beq	a5,zero,.L46
__isaforge_end_268:
__isaforge_begin_269:
	lui	a2,%hi(lift_level)
__isaforge_end_269:
__isaforge_begin_270:
	lw	a2,%lo(lift_level)(a2)
__isaforge_end_270:
__isaforge_begin_271:
	sgt	a5,a5,a2
__isaforge_end_271:
__isaforge_begin_272:
	seqz	a5,a5
__isaforge_end_272:
__isaforge_begin_273:
	addi	a2,a5,1
__isaforge_end_273:
.L46:
__isaforge_begin_274:
	li	a5,1
__isaforge_end_274:
__isaforge_begin_275:
	sw	a5,%lo(lift_loadPending)(a3)
__isaforge_end_275:
__isaforge_begin_276:
	lui	a5,%hi(lift_loadSensor)
__isaforge_end_276:
__isaforge_begin_277:
	sw	a2,%lo(lift_cmd)(a4)
__isaforge_end_277:
__isaforge_begin_278:
	sw	zero,%lo(lift_loadSensor)(a5)
__isaforge_end_278:
__isaforge_begin_279:
	j	.L42
__isaforge_end_279:
.L45:
__isaforge_begin_280:
	lw	a3,24(a5)
__isaforge_end_280:
__isaforge_begin_281:
	beq	a3,zero,.L47
__isaforge_end_281:
__isaforge_begin_282:
	lw	a5,4(a5)
__isaforge_end_282:
__isaforge_begin_283:
	beq	a5,zero,.L48
__isaforge_end_283:
.L41:
__isaforge_begin_284:
	lw	a5,%lo(lift_cmd)(a4)
__isaforge_end_284:
__isaforge_begin_285:
	bne	a5,zero,.L42
__isaforge_end_285:
__isaforge_begin_286:
	ret
__isaforge_end_286:
.L47:
__isaforge_begin_287:
	lw	a3,28(a5)
__isaforge_end_287:
__isaforge_begin_288:
	beq	a3,zero,.L41
__isaforge_end_288:
__isaforge_begin_289:
	lw	a5,8(a5)
__isaforge_end_289:
__isaforge_begin_290:
	bne	a5,zero,.L41
__isaforge_end_290:
__isaforge_begin_291:
	li	a5,2
__isaforge_end_291:
__isaforge_begin_292:
	j	.L62
__isaforge_end_292:
	.size	lift_check_cmd, .-lift_check_cmd
	.section	.text.lift_do_impulse,"ax",@progbits
	.align	2
	.globl	lift_do_impulse
	.type	lift_do_impulse, @function
lift_do_impulse:
__isaforge_begin_293:
	lui	a6,%hi(lift_timImp)
__isaforge_end_293:
__isaforge_begin_294:
	lw	a5,%lo(lift_timImp)(a6)
__isaforge_end_294:
__isaforge_begin_295:
	lui	a7,%hi(lift_lastImp)
__isaforge_end_295:
__isaforge_begin_296:
	beq	a0,zero,.L64
__isaforge_end_296:
__isaforge_begin_297:
	lw	a4,%lo(lift_lastImp)(a7)
__isaforge_end_297:
__isaforge_begin_298:
	bne	a4,zero,.L64
__isaforge_end_298:
__isaforge_begin_299:
	bne	a1,zero,.L65
__isaforge_end_299:
__isaforge_begin_300:
	ble	a5,zero,.L64
__isaforge_end_300:
.L65:
__isaforge_begin_301:
	lui	a1,%hi(lift_directionUp)
__isaforge_end_301:
__isaforge_begin_302:
	lw	a1,%lo(lift_directionUp)(a1)
__isaforge_end_302:
__isaforge_begin_303:
	lui	a3,%hi(lift_cnt)
__isaforge_end_303:
__isaforge_begin_304:
	lw	a4,%lo(lift_cnt)(a3)
__isaforge_end_304:
__isaforge_begin_305:
	beq	a1,zero,.L66
__isaforge_end_305:
__isaforge_begin_306:
	addi	a4,a4,1
__isaforge_end_306:
.L80:
__isaforge_begin_307:
	sw	a4,%lo(lift_cnt)(a3)
__isaforge_end_307:
.L64:
__isaforge_begin_308:
	beq	a2,zero,.L67
__isaforge_end_308:
__isaforge_begin_309:
	lui	a4,%hi(lift_cnt)
__isaforge_end_309:
__isaforge_begin_310:
	sw	zero,%lo(lift_cnt)(a4)
__isaforge_end_310:
__isaforge_begin_311:
	li	a3,1
__isaforge_end_311:
__isaforge_begin_312:
	lui	a4,%hi(lift_cntValid)
__isaforge_end_312:
__isaforge_begin_313:
	sw	a3,%lo(lift_cntValid)(a4)
__isaforge_end_313:
.L67:
__isaforge_begin_314:
	sw	a0,%lo(lift_lastImp)(a7)
__isaforge_end_314:
__isaforge_begin_315:
	ble	a5,zero,.L63
__isaforge_end_315:
__isaforge_begin_316:
	addi	a5,a5,-1
__isaforge_end_316:
__isaforge_begin_317:
	sw	a5,%lo(lift_timImp)(a6)
__isaforge_end_317:
__isaforge_begin_318:
	bne	a5,zero,.L63
__isaforge_end_318:
__isaforge_begin_319:
	lui	a5,%hi(lift_cmd)
__isaforge_end_319:
__isaforge_begin_320:
	lw	a4,%lo(lift_cmd)(a5)
__isaforge_end_320:
__isaforge_begin_321:
	beq	a4,zero,.L63
__isaforge_end_321:
__isaforge_begin_322:
	sw	zero,%lo(lift_cmd)(a5)
__isaforge_end_322:
.L63:
__isaforge_begin_323:
	ret
__isaforge_end_323:
.L66:
__isaforge_begin_324:
	addi	a4,a4,-1
__isaforge_end_324:
__isaforge_begin_325:
	j	.L80
__isaforge_end_325:
	.size	lift_do_impulse, .-lift_do_impulse
	.section	.text.lift_wait_for_motor_start,"ax",@progbits
	.align	2
	.globl	lift_wait_for_motor_start
	.type	lift_wait_for_motor_start, @function
lift_wait_for_motor_start:
__isaforge_begin_326:
	lui	a4,%hi(lift_timMotor)
__isaforge_end_326:
__isaforge_begin_327:
	lw	a5,%lo(lift_timMotor)(a4)
__isaforge_end_327:
__isaforge_begin_328:
	lui	a3,%hi(lift_directionUp)
__isaforge_end_328:
__isaforge_begin_329:
	addi	a5,a5,-1
__isaforge_end_329:
__isaforge_begin_330:
	sw	a5,%lo(lift_timMotor)(a4)
__isaforge_end_330:
__isaforge_begin_331:
	lui	a5,%hi(lift_cmd)
__isaforge_end_331:
__isaforge_begin_332:
	lw	a4,%lo(lift_cmd)(a5)
__isaforge_end_332:
__isaforge_begin_333:
	andi	a5,a4,-3
__isaforge_end_333:
__isaforge_begin_334:
	addi	a5,a5,-1
__isaforge_end_334:
__isaforge_begin_335:
	seqz	a5,a5
__isaforge_end_335:
__isaforge_begin_336:
	sw	a5,%lo(lift_directionUp)(a3)
__isaforge_end_336:
__isaforge_begin_337:
	lui	a3,%hi(lift_ctrl_io_out+4)
__isaforge_end_337:
__isaforge_begin_338:
	sw	a5,%lo(lift_ctrl_io_out+4)(a3)
__isaforge_end_338:
__isaforge_begin_339:
	lui	a5,%hi(lift_cntValid)
__isaforge_end_339:
__isaforge_begin_340:
	lw	a2,%lo(lift_cntValid)(a5)
__isaforge_end_340:
__isaforge_begin_341:
	lui	a3,%hi(lift_endCnt)
__isaforge_end_341:
__isaforge_begin_342:
	lui	a5,%hi(lift_cnt)
__isaforge_end_342:
__isaforge_begin_343:
	bne	a2,zero,.L82
__isaforge_end_343:
__isaforge_begin_344:
	sw	zero,%lo(lift_cnt)(a5)
__isaforge_end_344:
__isaforge_begin_345:
	li	a2,3
__isaforge_end_345:
__isaforge_begin_346:
	lui	a5,%hi(lift_one_level)
__isaforge_end_346:
__isaforge_begin_347:
	lw	a5,%lo(lift_one_level)(a5)
__isaforge_end_347:
__isaforge_begin_348:
	bne	a4,a2,.L83
__isaforge_end_348:
.L87:
__isaforge_begin_349:
	sw	a5,%lo(lift_endCnt)(a3)
__isaforge_end_349:
.L81:
__isaforge_begin_350:
	ret
__isaforge_end_350:
.L83:
__isaforge_begin_351:
	neg	a5,a5
__isaforge_end_351:
__isaforge_begin_352:
	j	.L87
__isaforge_end_352:
.L82:
__isaforge_begin_353:
	lw	a5,%lo(lift_cnt)(a5)
__isaforge_end_353:
__isaforge_begin_354:
	sw	a5,%lo(lift_endCnt)(a3)
__isaforge_end_354:
__isaforge_begin_355:
	li	a5,3
__isaforge_end_355:
__isaforge_begin_356:
	bne	a4,a5,.L85
__isaforge_end_356:
__isaforge_begin_357:
	lui	a5,%hi(lift_level)
__isaforge_end_357:
__isaforge_begin_358:
	lw	a5,%lo(lift_level)(a5)
__isaforge_end_358:
__isaforge_begin_359:
	addi	a5,a5,1
__isaforge_end_359:
.L86:
__isaforge_begin_360:
	addi	a5,a5,-1
__isaforge_end_360:
__isaforge_begin_361:
	li	a4,13
__isaforge_end_361:
__isaforge_begin_362:
	bgtu	a5,a4,.L81
__isaforge_end_362:
__isaforge_begin_363:
	lui	a4,%hi(lift_levelPos)
__isaforge_end_363:
__isaforge_begin_364:
	slli	a5,a5,2
__isaforge_end_364:
__isaforge_begin_365:
	addi	a4,a4,%lo(lift_levelPos)
__isaforge_end_365:
__isaforge_begin_366:
	add	a5,a4,a5
__isaforge_end_366:
__isaforge_begin_367:
	lw	a5,0(a5)
__isaforge_end_367:
__isaforge_begin_368:
	j	.L87
__isaforge_end_368:
.L85:
__isaforge_begin_369:
	li	a5,4
__isaforge_end_369:
__isaforge_begin_370:
	bne	a4,a5,.L81
__isaforge_end_370:
__isaforge_begin_371:
	lui	a5,%hi(lift_level)
__isaforge_end_371:
__isaforge_begin_372:
	lw	a5,%lo(lift_level)(a5)
__isaforge_end_372:
__isaforge_begin_373:
	addi	a5,a5,-1
__isaforge_end_373:
__isaforge_begin_374:
	j	.L86
__isaforge_end_374:
	.size	lift_wait_for_motor_start, .-lift_wait_for_motor_start
	.section	.text.lift_check_run,"ax",@progbits
	.align	2
	.globl	lift_check_run
	.type	lift_check_run, @function
lift_check_run:
__isaforge_begin_375:
	lui	a5,%hi(lift_cmd)
__isaforge_end_375:
__isaforge_begin_376:
	lw	a0,%lo(lift_cmd)(a5)
__isaforge_end_376:
__isaforge_begin_377:
	li	a5,3
__isaforge_end_377:
__isaforge_begin_378:
	bne	a0,a5,.L89
__isaforge_end_378:
__isaforge_begin_379:
	lui	a5,%hi(lift_endCnt)
__isaforge_end_379:
__isaforge_begin_380:
	lw	a5,%lo(lift_endCnt)(a5)
__isaforge_end_380:
__isaforge_begin_381:
	lui	a4,%hi(lift_cnt)
__isaforge_end_381:
__isaforge_begin_382:
	lw	a4,%lo(lift_cnt)(a4)
__isaforge_end_382:
__isaforge_begin_383:
	addi	a5,a5,-1
__isaforge_end_383:
__isaforge_begin_384:
	ble	a5,a4,.L90
__isaforge_end_384:
__isaforge_begin_385:
	lui	a5,%hi(lift_ctrl_io_in+4)
__isaforge_end_385:
__isaforge_begin_386:
	lw	a0,%lo(lift_ctrl_io_in+4)(a5)
__isaforge_end_386:
.L113:
__isaforge_begin_387:
	seqz	a0,a0
__isaforge_end_387:
__isaforge_begin_388:
	ret
__isaforge_end_388:
.L89:
__isaforge_begin_389:
	li	a5,4
__isaforge_end_389:
__isaforge_begin_390:
	bne	a0,a5,.L92
__isaforge_end_390:
__isaforge_begin_391:
	lui	a5,%hi(lift_endCnt)
__isaforge_end_391:
__isaforge_begin_392:
	lw	a5,%lo(lift_endCnt)(a5)
__isaforge_end_392:
__isaforge_begin_393:
	lui	a4,%hi(lift_cnt)
__isaforge_end_393:
__isaforge_begin_394:
	lw	a4,%lo(lift_cnt)(a4)
__isaforge_end_394:
__isaforge_begin_395:
	addi	a5,a5,1
__isaforge_end_395:
__isaforge_begin_396:
	bge	a5,a4,.L90
__isaforge_end_396:
__isaforge_begin_397:
	lui	a5,%hi(lift_ctrl_io_in+8)
__isaforge_end_397:
__isaforge_begin_398:
	lw	a0,%lo(lift_ctrl_io_in+8)(a5)
__isaforge_end_398:
__isaforge_begin_399:
	j	.L113
__isaforge_end_399:
.L92:
__isaforge_begin_400:
	li	a5,1
__isaforge_end_400:
__isaforge_begin_401:
	bne	a0,a5,.L93
__isaforge_end_401:
__isaforge_begin_402:
	lui	a4,%hi(lift_loadPending)
__isaforge_end_402:
__isaforge_begin_403:
	lw	a3,%lo(lift_loadPending)(a4)
__isaforge_end_403:
__isaforge_begin_404:
	lui	a5,%hi(lift_ctrl_io_in)
__isaforge_end_404:
__isaforge_begin_405:
	addi	a5,a5,%lo(lift_ctrl_io_in)
__isaforge_end_405:
__isaforge_begin_406:
	beq	a3,zero,.L94
__isaforge_end_406:
__isaforge_begin_407:
	lw	a3,12(a5)
__isaforge_end_407:
__isaforge_begin_408:
	beq	a3,zero,.L94
__isaforge_end_408:
__isaforge_begin_409:
	lui	a5,%hi(lift_level)
__isaforge_end_409:
__isaforge_begin_410:
	lw	a3,%lo(lift_level)(a5)
__isaforge_end_410:
__isaforge_begin_411:
	lui	a5,%hi(lift_loadLevel)
__isaforge_end_411:
__isaforge_begin_412:
	sw	a3,%lo(lift_loadLevel)(a5)
__isaforge_end_412:
.L112:
__isaforge_begin_413:
	sw	zero,%lo(lift_loadPending)(a4)
__isaforge_end_413:
.L90:
__isaforge_begin_414:
	li	a0,0
__isaforge_end_414:
__isaforge_begin_415:
	ret
__isaforge_end_415:
.L94:
__isaforge_begin_416:
	lw	a5,4(a5)
__isaforge_end_416:
__isaforge_begin_417:
	bne	a5,zero,.L112
__isaforge_end_417:
__isaforge_begin_418:
	ret
__isaforge_end_418:
.L93:
__isaforge_begin_419:
	li	a5,2
__isaforge_end_419:
__isaforge_begin_420:
	bne	a0,a5,.L90
__isaforge_end_420:
__isaforge_begin_421:
	lui	a2,%hi(lift_loadPending)
__isaforge_end_421:
__isaforge_begin_422:
	lw	a4,%lo(lift_loadPending)(a2)
__isaforge_end_422:
__isaforge_begin_423:
	lui	a5,%hi(lift_ctrl_io_in)
__isaforge_end_423:
__isaforge_begin_424:
	addi	a5,a5,%lo(lift_ctrl_io_in)
__isaforge_end_424:
__isaforge_begin_425:
	beq	a4,zero,.L95
__isaforge_end_425:
__isaforge_begin_426:
	lui	a4,%hi(lift_loadSensor)
__isaforge_end_426:
__isaforge_begin_427:
	lw	a1,%lo(lift_loadSensor)(a4)
__isaforge_end_427:
__isaforge_begin_428:
	lw	a3,12(a5)
__isaforge_end_428:
__isaforge_begin_429:
	beq	a1,zero,.L96
__isaforge_end_429:
__isaforge_begin_430:
	bne	a3,zero,.L96
__isaforge_end_430:
__isaforge_begin_431:
	lui	a5,%hi(lift_level)
__isaforge_end_431:
__isaforge_begin_432:
	sw	zero,%lo(lift_loadSensor)(a4)
__isaforge_end_432:
__isaforge_begin_433:
	lw	a4,%lo(lift_level)(a5)
__isaforge_end_433:
__isaforge_begin_434:
	lui	a5,%hi(lift_loadLevel)
__isaforge_end_434:
__isaforge_begin_435:
	sw	zero,%lo(lift_loadPending)(a2)
__isaforge_end_435:
__isaforge_begin_436:
	sw	a4,%lo(lift_loadLevel)(a5)
__isaforge_end_436:
__isaforge_begin_437:
	j	.L90
__isaforge_end_437:
.L96:
__isaforge_begin_438:
	sw	a3,%lo(lift_loadSensor)(a4)
__isaforge_end_438:
.L95:
__isaforge_begin_439:
	lw	a0,8(a5)
__isaforge_end_439:
__isaforge_begin_440:
	j	.L113
__isaforge_end_440:
	.size	lift_check_run, .-lift_check_run
	.section	.text.lift_do_cmd,"ax",@progbits
	.align	2
	.globl	lift_do_cmd
	.type	lift_do_cmd, @function
lift_do_cmd:
__isaforge_begin_441:
	lui	a5,%hi(lift_timMotor)
__isaforge_end_441:
__isaforge_begin_442:
	lw	a5,%lo(lift_timMotor)(a5)
__isaforge_end_442:
__isaforge_begin_443:
	ble	a5,zero,.L115
__isaforge_end_443:
__isaforge_begin_444:
	tail	lift_wait_for_motor_start
__isaforge_end_444:
.L115:
__isaforge_begin_445:
	addi	sp,sp,-16
__isaforge_end_445:
__isaforge_begin_446:
	sw	ra,12(sp)
__isaforge_end_446:
__isaforge_begin_447:
	call	lift_check_run
__isaforge_end_447:
__isaforge_begin_448:
	lui	a5,%hi(lift_ctrl_io_out)
__isaforge_end_448:
__isaforge_begin_449:
	lw	a4,%lo(lift_ctrl_io_out)(a5)
__isaforge_end_449:
__isaforge_begin_450:
	beq	a4,zero,.L116
__isaforge_end_450:
__isaforge_begin_451:
	slli	a3,a0,31
__isaforge_end_451:
__isaforge_begin_452:
	srli	a4,a3,31
__isaforge_end_452:
__isaforge_begin_453:
	bne	a4,zero,.L116
__isaforge_end_453:
__isaforge_begin_454:
	lui	a4,%hi(lift_cmd)
__isaforge_end_454:
__isaforge_begin_455:
	li	a3,99
__isaforge_end_455:
__isaforge_begin_456:
	sw	a3,%lo(lift_cmd)(a4)
__isaforge_end_456:
__isaforge_begin_457:
	lui	a4,%hi(lift_timImp)
__isaforge_end_457:
__isaforge_begin_458:
	li	a3,50
__isaforge_end_458:
__isaforge_begin_459:
	sw	a3,%lo(lift_timImp)(a4)
__isaforge_end_459:
.L116:
__isaforge_begin_460:
	lw	ra,12(sp)
__isaforge_end_460:
__isaforge_begin_461:
	sw	a0,%lo(lift_ctrl_io_out)(a5)
__isaforge_end_461:
__isaforge_begin_462:
	addi	sp,sp,16
__isaforge_end_462:
__isaforge_begin_463:
	jr	ra
__isaforge_end_463:
	.size	lift_do_cmd, .-lift_do_cmd
	.section	.text.lift_ctrl_loop,"ax",@progbits
	.align	2
	.globl	lift_ctrl_loop
	.type	lift_ctrl_loop, @function
lift_ctrl_loop:
__isaforge_begin_464:
	lui	a5,%hi(lift_cmd)
__isaforge_end_464:
__isaforge_begin_465:
	lw	a5,%lo(lift_cmd)(a5)
__isaforge_end_465:
__isaforge_begin_466:
	addi	sp,sp,-16
__isaforge_end_466:
__isaforge_begin_467:
	sw	ra,12(sp)
__isaforge_end_467:
__isaforge_begin_468:
	bne	a5,zero,.L126
__isaforge_end_468:
__isaforge_begin_469:
	call	lift_check_cmd
__isaforge_end_469:
.L127:
__isaforge_begin_470:
	call	lift_check_level
__isaforge_end_470:
__isaforge_begin_471:
	lui	a3,%hi(lift_dbgCnt)
__isaforge_end_471:
__isaforge_begin_472:
	lw	a5,%lo(lift_dbgCnt)(a3)
__isaforge_end_472:
__isaforge_begin_473:
	lw	ra,12(sp)
__isaforge_end_473:
__isaforge_begin_474:
	lui	a2,%hi(lift_ctrl_io_led+52)
__isaforge_end_474:
__isaforge_begin_475:
	srli	a4,a5,7
__isaforge_end_475:
__isaforge_begin_476:
	andi	a4,a4,1
__isaforge_end_476:
__isaforge_begin_477:
	addi	a5,a5,1
__isaforge_end_477:
__isaforge_begin_478:
	sw	a4,%lo(lift_ctrl_io_led+52)(a2)
__isaforge_end_478:
__isaforge_begin_479:
	sw	a5,%lo(lift_dbgCnt)(a3)
__isaforge_end_479:
__isaforge_begin_480:
	addi	sp,sp,16
__isaforge_end_480:
__isaforge_begin_481:
	jr	ra
__isaforge_end_481:
.L126:
__isaforge_begin_482:
	lui	a5,%hi(lift_ctrl_io_in)
__isaforge_end_482:
__isaforge_begin_483:
	addi	a5,a5,%lo(lift_ctrl_io_in)
__isaforge_end_483:
__isaforge_begin_484:
	lui	a4,%hi(lift_ctrl_io_out)
__isaforge_end_484:
__isaforge_begin_485:
	lw	a2,8(a5)
__isaforge_end_485:
__isaforge_begin_486:
	lw	a1,%lo(lift_ctrl_io_out)(a4)
__isaforge_end_486:
__isaforge_begin_487:
	lw	a0,0(a5)
__isaforge_end_487:
__isaforge_begin_488:
	call	lift_do_impulse
__isaforge_end_488:
__isaforge_begin_489:
	call	lift_do_cmd
__isaforge_end_489:
__isaforge_begin_490:
	j	.L127
__isaforge_end_490:
	.size	lift_ctrl_loop, .-lift_ctrl_loop
	.section	.text.lift_controller,"ax",@progbits
	.align	2
	.globl	lift_controller
	.type	lift_controller, @function
lift_controller:
__isaforge_begin_491:
	addi	sp,sp,-16
__isaforge_end_491:
__isaforge_begin_492:
	sw	ra,12(sp)
__isaforge_end_492:
__isaforge_begin_493:
	call	lift_ctrl_get_vals
__isaforge_end_493:
__isaforge_begin_494:
	call	lift_ctrl_loop
__isaforge_end_494:
__isaforge_begin_495:
	lw	ra,12(sp)
__isaforge_end_495:
__isaforge_begin_496:
	addi	sp,sp,16
__isaforge_end_496:
__isaforge_begin_497:
	tail	lift_ctrl_set_vals
__isaforge_end_497:
	.size	lift_controller, .-lift_controller
	.section	.text.lift_main,"ax",@progbits
	.align	2
	.globl	lift_main
	.type	lift_main, @function
lift_main:
__isaforge_begin_498:
	addi	sp,sp,-32
__isaforge_end_498:
__isaforge_begin_499:
	sw	s0,24(sp)
__isaforge_end_499:
__isaforge_begin_500:
	sw	s1,20(sp)
__isaforge_end_500:
__isaforge_begin_501:
	sw	s2,16(sp)
__isaforge_end_501:
__isaforge_begin_502:
	sw	s3,12(sp)
__isaforge_end_502:
__isaforge_begin_503:
	sw	s4,8(sp)
__isaforge_end_503:
__isaforge_begin_504:
	sw	ra,28(sp)
__isaforge_end_504:
__isaforge_begin_505:
	li	s0,1001
__isaforge_end_505:
__isaforge_begin_506:
	lui	s4,%hi(lift_simio_in)
__isaforge_end_506:
__isaforge_begin_507:
	lui	s3,%hi(lift_simio_adc1)
__isaforge_end_507:
__isaforge_begin_508:
	lui	s2,%hi(lift_simio_adc2)
__isaforge_end_508:
__isaforge_begin_509:
	lui	s1,%hi(lift_simio_adc3)
__isaforge_end_509:
.L132:
__isaforge_begin_510:
	sw	zero,%lo(lift_simio_in)(s4)
__isaforge_end_510:
__isaforge_begin_511:
	sw	zero,%lo(lift_simio_adc1)(s3)
__isaforge_end_511:
__isaforge_begin_512:
	sw	zero,%lo(lift_simio_adc2)(s2)
__isaforge_end_512:
__isaforge_begin_513:
	addi	s0,s0,-1
__isaforge_end_513:
__isaforge_begin_514:
	sw	zero,%lo(lift_simio_adc3)(s1)
__isaforge_end_514:
__isaforge_begin_515:
	call	lift_controller
__isaforge_end_515:
__isaforge_begin_516:
	bne	s0,zero,.L132
__isaforge_end_516:
__isaforge_begin_517:
	lw	ra,28(sp)
__isaforge_end_517:
__isaforge_begin_518:
	lw	s0,24(sp)
__isaforge_end_518:
__isaforge_begin_519:
	lw	s1,20(sp)
__isaforge_end_519:
__isaforge_begin_520:
	lw	s2,16(sp)
__isaforge_end_520:
__isaforge_begin_521:
	lw	s3,12(sp)
__isaforge_end_521:
__isaforge_begin_522:
	lw	s4,8(sp)
__isaforge_end_522:
__isaforge_begin_523:
	addi	sp,sp,32
__isaforge_end_523:
__isaforge_begin_524:
	jr	ra
__isaforge_end_524:
	.size	lift_main, .-lift_main
	.section	.text.isaforge_tacle_lift_original_main,"ax",@progbits
	.align	2
	.globl	isaforge_tacle_lift_original_main
	.type	isaforge_tacle_lift_original_main, @function
isaforge_tacle_lift_original_main:
__isaforge_begin_525:
	addi	sp,sp,-16
__isaforge_end_525:
__isaforge_begin_526:
	sw	ra,12(sp)
__isaforge_end_526:
__isaforge_begin_527:
	call	lift_init
__isaforge_end_527:
__isaforge_begin_528:
	call	lift_main
__isaforge_end_528:
__isaforge_begin_529:
	lui	a5,%hi(lift_checksum)
__isaforge_end_529:
__isaforge_begin_530:
	lw	a0,%lo(lift_checksum)(a5)
__isaforge_end_530:
__isaforge_begin_531:
	lw	ra,12(sp)
__isaforge_end_531:
__isaforge_begin_532:
	li	a5,-4005888
__isaforge_end_532:
__isaforge_begin_533:
	add	a0,a0,a5
__isaforge_end_533:
__isaforge_begin_534:
	snez	a0,a0
__isaforge_end_534:
__isaforge_begin_535:
	addi	sp,sp,16
__isaforge_end_535:
__isaforge_begin_536:
	jr	ra
__isaforge_end_536:
	.size	isaforge_tacle_lift_original_main, .-isaforge_tacle_lift_original_main
	.section	.text.initialise_benchmark,"ax",@progbits
	.align	2
	.globl	initialise_benchmark
	.type	initialise_benchmark, @function
initialise_benchmark:
__isaforge_begin_537:
	tail	lift_init
__isaforge_end_537:
	.size	initialise_benchmark, .-initialise_benchmark
	.section	.text.warm_caches,"ax",@progbits
	.align	2
	.globl	warm_caches
	.type	warm_caches, @function
warm_caches:
__isaforge_begin_538:
	ret
__isaforge_end_538:
	.size	warm_caches, .-warm_caches
	.section	.text.benchmark,"ax",@progbits
	.align	2
	.globl	benchmark
	.type	benchmark, @function
benchmark:
__isaforge_begin_539:
	addi	sp,sp,-16
__isaforge_end_539:
__isaforge_begin_540:
	sw	ra,12(sp)
__isaforge_end_540:
__isaforge_begin_541:
	call	lift_main
__isaforge_end_541:
__isaforge_begin_542:
	lui	a5,%hi(lift_checksum)
__isaforge_end_542:
__isaforge_begin_543:
	lw	a0,%lo(lift_checksum)(a5)
__isaforge_end_543:
__isaforge_begin_544:
	lw	ra,12(sp)
__isaforge_end_544:
__isaforge_begin_545:
	li	a5,-4005888
__isaforge_end_545:
__isaforge_begin_546:
	add	a0,a0,a5
__isaforge_end_546:
__isaforge_begin_547:
	snez	a0,a0
__isaforge_end_547:
__isaforge_begin_548:
	addi	sp,sp,16
__isaforge_end_548:
__isaforge_begin_549:
	jr	ra
__isaforge_end_549:
	.size	benchmark, .-benchmark
	.section	.text.verify_benchmark,"ax",@progbits
	.align	2
	.globl	verify_benchmark
	.type	verify_benchmark, @function
verify_benchmark:
__isaforge_begin_550:
	bne	a0,zero,.L143
__isaforge_end_550:
__isaforge_begin_551:
	lui	a5,%hi(lift_checksum)
__isaforge_end_551:
__isaforge_begin_552:
	lw	a0,%lo(lift_checksum)(a5)
__isaforge_end_552:
__isaforge_begin_553:
	li	a5,-4005888
__isaforge_end_553:
__isaforge_begin_554:
	add	a0,a0,a5
__isaforge_end_554:
__isaforge_begin_555:
	seqz	a0,a0
__isaforge_end_555:
__isaforge_begin_556:
	ret
__isaforge_end_556:
.L143:
__isaforge_begin_557:
	li	a0,0
__isaforge_end_557:
__isaforge_begin_558:
	ret
__isaforge_end_558:
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
