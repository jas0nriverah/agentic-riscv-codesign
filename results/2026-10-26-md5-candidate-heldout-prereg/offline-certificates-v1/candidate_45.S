	.file	"program.c"
	.option nopic
	.option norelax
	.attribute arch, "rv32i2p1_zicsr2p0"
	.attribute unaligned_access, 0
	.attribute stack_align, 16
	.text
	.section	.text._nettle_md5_compress,"ax",@progbits
	.align	2
	.globl	_nettle_md5_compress
	.type	_nettle_md5_compress, @function
_nettle_md5_compress:
__isaforge_begin_0:
	addi	sp,sp,-112
__isaforge_end_0:
__isaforge_begin_1:
	sw	s0,108(sp)
__isaforge_end_1:
__isaforge_begin_2:
	sw	s1,104(sp)
__isaforge_end_2:
__isaforge_begin_3:
	sw	s2,100(sp)
__isaforge_end_3:
__isaforge_begin_4:
	sw	s3,96(sp)
__isaforge_end_4:
__isaforge_begin_5:
	sw	s4,92(sp)
__isaforge_end_5:
__isaforge_begin_6:
	sw	s5,88(sp)
__isaforge_end_6:
__isaforge_begin_7:
	sw	s6,84(sp)
__isaforge_end_7:
__isaforge_begin_8:
	sw	s7,80(sp)
__isaforge_end_8:
__isaforge_begin_9:
	sw	s8,76(sp)
__isaforge_end_9:
__isaforge_begin_10:
	sw	s9,72(sp)
__isaforge_end_10:
__isaforge_begin_11:
	sw	s10,68(sp)
__isaforge_end_11:
__isaforge_begin_12:
	li	a5,0
__isaforge_end_12:
__isaforge_begin_13:
	li	a6,64
__isaforge_end_13:
.L2:
__isaforge_begin_14:
	add	a2,a1,a5
__isaforge_end_14:
__isaforge_begin_15:
	lbu	a4,1(a2)
__isaforge_end_15:
__isaforge_begin_16:
	lbu	a3,0(a2)
__isaforge_end_16:
__isaforge_begin_17:
	add	a7,sp,a5
__isaforge_end_17:
__isaforge_begin_18:
	slli	a4,a4,8
__isaforge_end_18:
__isaforge_begin_19:
	or	a4,a4,a3
__isaforge_end_19:
__isaforge_begin_20:
	lbu	a3,2(a2)
__isaforge_end_20:
__isaforge_begin_21:
	addi	a5,a5,4
__isaforge_end_21:
__isaforge_begin_22:
	slli	a3,a3,16
__isaforge_end_22:
__isaforge_begin_23:
	or	a3,a3,a4
__isaforge_end_23:
__isaforge_begin_24:
	lbu	a4,3(a2)
__isaforge_end_24:
__isaforge_begin_25:
	slli	a4,a4,24
__isaforge_end_25:
__isaforge_begin_26:
	or	a4,a4,a3
__isaforge_end_26:
__isaforge_begin_27:
	sw	a4,0(a7)
__isaforge_end_27:
__isaforge_begin_28:
	bne	a5,a6,.L2
__isaforge_end_28:
__isaforge_begin_29:
	lw	s6,0(sp)
__isaforge_end_29:
__isaforge_begin_30:
	lw	s7,8(a0)
__isaforge_end_30:
__isaforge_begin_31:
	lw	s8,12(a0)
__isaforge_end_31:
__isaforge_begin_32:
	lw	a5,0(a0)
__isaforge_end_32:
__isaforge_begin_33:
	li	a4,-680878080
__isaforge_end_33:
__isaforge_begin_34:
	lw	a1,4(a0)
__isaforge_end_34:
__isaforge_begin_35:
	addi	a4,a4,1144
__isaforge_end_35:
__isaforge_begin_36:
	add	a4,s6,a4
__isaforge_end_36:
__isaforge_begin_37:
	add	a4,a4,a5
__isaforge_end_37:
__isaforge_begin_38:
	xor	a5,s7,s8
__isaforge_end_38:
__isaforge_begin_39:
	and	a5,a5,a1
__isaforge_end_39:
__isaforge_begin_40:
	xor	a5,a5,s8
__isaforge_end_40:
__isaforge_begin_41:
	add	a5,a5,a4
__isaforge_end_41:
__isaforge_begin_42:
	lw	t2,4(sp)
__isaforge_end_42:
__isaforge_begin_43:
	srli	a4,a5,25
__isaforge_end_43:
__isaforge_begin_44:
	slli	a5,a5,7
__isaforge_end_44:
__isaforge_begin_45:
	add	a5,a5,a4
__isaforge_end_45:
__isaforge_begin_46:
	li	a4,-389566464
__isaforge_end_46:
__isaforge_begin_47:
	add	a5,a1,a5
__isaforge_end_47:
__isaforge_begin_48:
	xor	a2,a1,s7
__isaforge_end_48:
__isaforge_begin_49:
	addi	a4,a4,1878
__isaforge_end_49:
__isaforge_begin_50:
	add	a4,t2,a4
__isaforge_end_50:
__isaforge_begin_51:
	and	a2,a2,a5
__isaforge_end_51:
__isaforge_begin_52:
	add	a4,a4,s8
__isaforge_end_52:
__isaforge_begin_53:
	xor	a2,a2,s7
__isaforge_end_53:
__isaforge_begin_54:
	add	a2,a2,a4
__isaforge_end_54:
__isaforge_begin_55:
	lw	a7,8(sp)
__isaforge_end_55:
__isaforge_begin_56:
	srli	a4,a2,20
__isaforge_end_56:
__isaforge_begin_57:
	slli	a2,a2,12
__isaforge_end_57:
__isaforge_begin_58:
	add	a2,a2,a4
__isaforge_end_58:
__isaforge_begin_59:
	li	a4,606105600
__isaforge_end_59:
__isaforge_begin_60:
	add	a2,a5,a2
__isaforge_end_60:
__isaforge_begin_61:
	xor	a3,a1,a5
__isaforge_end_61:
__isaforge_begin_62:
	addi	a4,a4,219
__isaforge_end_62:
__isaforge_begin_63:
	add	a4,a7,a4
__isaforge_end_63:
__isaforge_begin_64:
	and	a3,a3,a2
__isaforge_end_64:
__isaforge_begin_65:
	add	a4,a4,s7
__isaforge_end_65:
__isaforge_begin_66:
	xor	a3,a3,a1
__isaforge_end_66:
__isaforge_begin_67:
	add	a3,a3,a4
__isaforge_end_67:
__isaforge_begin_68:
	lw	s1,12(sp)
__isaforge_end_68:
__isaforge_begin_69:
	srli	a4,a3,15
__isaforge_end_69:
__isaforge_begin_70:
	slli	a3,a3,17
__isaforge_end_70:
__isaforge_begin_71:
	add	a3,a3,a4
__isaforge_end_71:
__isaforge_begin_72:
	li	a6,-1044525056
__isaforge_end_72:
__isaforge_begin_73:
	add	a3,a2,a3
__isaforge_end_73:
__isaforge_begin_74:
	xor	a4,a5,a2
__isaforge_end_74:
__isaforge_begin_75:
	addi	a6,a6,-274
__isaforge_end_75:
__isaforge_begin_76:
	add	a6,s1,a6
__isaforge_end_76:
__isaforge_begin_77:
	and	a4,a4,a3
__isaforge_end_77:
__isaforge_begin_78:
	add	a6,a6,a1
__isaforge_end_78:
__isaforge_begin_79:
	xor	a4,a4,a5
__isaforge_end_79:
__isaforge_begin_80:
	add	a4,a4,a6
__isaforge_end_80:
__isaforge_begin_81:
	lw	t3,16(sp)
__isaforge_end_81:
__isaforge_begin_82:
	srli	a6,a4,10
__isaforge_end_82:
__isaforge_begin_83:
	slli	a4,a4,22
__isaforge_end_83:
__isaforge_begin_84:
	add	a4,a4,a6
__isaforge_end_84:
__isaforge_begin_85:
	li	a6,-176418816
__isaforge_end_85:
__isaforge_begin_86:
	addi	a6,a6,-81
__isaforge_end_86:
__isaforge_begin_87:
	add	a6,t3,a6
__isaforge_end_87:
__isaforge_begin_88:
	add	a4,a3,a4
__isaforge_end_88:
__isaforge_begin_89:
	add	a6,a6,a5
__isaforge_end_89:
__isaforge_begin_90:
	xor	a5,a2,a3
__isaforge_end_90:
__isaforge_begin_91:
	and	a5,a5,a4
__isaforge_end_91:
__isaforge_begin_92:
	xor	a5,a5,a2
__isaforge_end_92:
__isaforge_begin_93:
	add	a5,a5,a6
__isaforge_end_93:
__isaforge_begin_94:
	lw	s3,20(sp)
__isaforge_end_94:
__isaforge_begin_95:
	srli	a6,a5,25
__isaforge_end_95:
__isaforge_begin_96:
	slli	a5,a5,7
__isaforge_end_96:
__isaforge_begin_97:
	add	a5,a5,a6
__isaforge_end_97:
__isaforge_begin_98:
	li	a6,1200078848
__isaforge_end_98:
__isaforge_begin_99:
	addi	a6,a6,1578
__isaforge_end_99:
__isaforge_begin_100:
	add	a6,s3,a6
__isaforge_end_100:
__isaforge_begin_101:
	add	a5,a4,a5
__isaforge_end_101:
__isaforge_begin_102:
	add	a6,a6,a2
__isaforge_end_102:
__isaforge_begin_103:
	xor	a2,a3,a4
__isaforge_end_103:
__isaforge_begin_104:
	and	a2,a2,a5
__isaforge_end_104:
__isaforge_begin_105:
	xor	a2,a2,a3
__isaforge_end_105:
__isaforge_begin_106:
	add	a2,a2,a6
__isaforge_end_106:
__isaforge_begin_107:
	lw	t5,24(sp)
__isaforge_end_107:
__isaforge_begin_108:
	srli	a6,a2,20
__isaforge_end_108:
__isaforge_begin_109:
	slli	a2,a2,12
__isaforge_end_109:
__isaforge_begin_110:
	add	a2,a2,a6
__isaforge_end_110:
__isaforge_begin_111:
	li	a6,-1473232896
__isaforge_end_111:
__isaforge_begin_112:
	addi	a6,a6,1555
__isaforge_end_112:
__isaforge_begin_113:
	add	a6,t5,a6
__isaforge_end_113:
__isaforge_begin_114:
	add	a2,a5,a2
__isaforge_end_114:
__isaforge_begin_115:
	add	a6,a6,a3
__isaforge_end_115:
__isaforge_begin_116:
	xor	a3,a4,a5
__isaforge_end_116:
__isaforge_begin_117:
	and	a3,a3,a2
__isaforge_end_117:
__isaforge_begin_118:
	xor	a3,a3,a4
__isaforge_end_118:
__isaforge_begin_119:
	add	a3,a3,a6
__isaforge_end_119:
__isaforge_begin_120:
	lw	s5,28(sp)
__isaforge_end_120:
__isaforge_begin_121:
	srli	a6,a3,15
__isaforge_end_121:
__isaforge_begin_122:
	slli	a3,a3,17
__isaforge_end_122:
__isaforge_begin_123:
	add	a3,a3,a6
__isaforge_end_123:
__isaforge_begin_124:
	li	a6,-45707264
__isaforge_end_124:
__isaforge_begin_125:
	addi	a6,a6,1281
__isaforge_end_125:
__isaforge_begin_126:
	add	a6,s5,a6
__isaforge_end_126:
__isaforge_begin_127:
	add	a3,a2,a3
__isaforge_end_127:
__isaforge_begin_128:
	add	a6,a6,a4
__isaforge_end_128:
__isaforge_begin_129:
	xor	a4,a5,a2
__isaforge_end_129:
__isaforge_begin_130:
	and	a4,a4,a3
__isaforge_end_130:
__isaforge_begin_131:
	xor	a4,a4,a5
__isaforge_end_131:
__isaforge_begin_132:
	add	a4,a4,a6
__isaforge_end_132:
__isaforge_begin_133:
	lw	t0,32(sp)
__isaforge_end_133:
__isaforge_begin_134:
	srli	a6,a4,10
__isaforge_end_134:
__isaforge_begin_135:
	slli	a4,a4,22
__isaforge_end_135:
__isaforge_begin_136:
	add	a4,a4,a6
__isaforge_end_136:
__isaforge_begin_137:
	li	a6,1770037248
__isaforge_end_137:
__isaforge_begin_138:
	addi	a6,a6,-1832
__isaforge_end_138:
__isaforge_begin_139:
	add	a6,t0,a6
__isaforge_end_139:
__isaforge_begin_140:
	add	a4,a3,a4
__isaforge_end_140:
__isaforge_begin_141:
	add	a6,a6,a5
__isaforge_end_141:
__isaforge_begin_142:
	xor	a5,a2,a3
__isaforge_end_142:
__isaforge_begin_143:
	and	a5,a5,a4
__isaforge_end_143:
__isaforge_begin_144:
	xor	a5,a5,a2
__isaforge_end_144:
__isaforge_begin_145:
	add	a5,a5,a6
__isaforge_end_145:
__isaforge_begin_146:
	srli	a6,a5,25
__isaforge_end_146:
__isaforge_begin_147:
	slli	a5,a5,7
__isaforge_end_147:
__isaforge_begin_148:
	add	a5,a5,a6
__isaforge_end_148:
__isaforge_begin_149:
	lw	a6,36(sp)
__isaforge_end_149:
__isaforge_begin_150:
	li	t1,-1958416384
__isaforge_end_150:
__isaforge_begin_151:
	addi	t1,t1,1967
__isaforge_end_151:
__isaforge_begin_152:
	add	t1,a6,t1
__isaforge_end_152:
__isaforge_begin_153:
	add	a5,a4,a5
__isaforge_end_153:
__isaforge_begin_154:
	add	t1,t1,a2
__isaforge_end_154:
__isaforge_begin_155:
	xor	a2,a3,a4
__isaforge_end_155:
__isaforge_begin_156:
	and	a2,a2,a5
__isaforge_end_156:
__isaforge_begin_157:
	xor	a2,a2,a3
__isaforge_end_157:
__isaforge_begin_158:
	add	a2,a2,t1
__isaforge_end_158:
__isaforge_begin_159:
	lw	s0,40(sp)
__isaforge_end_159:
__isaforge_begin_160:
	srli	t1,a2,20
__isaforge_end_160:
__isaforge_begin_161:
	slli	a2,a2,12
__isaforge_end_161:
__isaforge_begin_162:
	add	a2,a2,t1
__isaforge_end_162:
__isaforge_begin_163:
	li	t1,-40960
__isaforge_end_163:
__isaforge_begin_164:
	addi	t1,t1,-1103
__isaforge_end_164:
__isaforge_begin_165:
	add	t1,s0,t1
__isaforge_end_165:
__isaforge_begin_166:
	add	a2,a5,a2
__isaforge_end_166:
__isaforge_begin_167:
	add	t1,t1,a3
__isaforge_end_167:
__isaforge_begin_168:
	xor	a3,a4,a5
__isaforge_end_168:
__isaforge_begin_169:
	and	a3,a3,a2
__isaforge_end_169:
__isaforge_begin_170:
	xor	a3,a3,a4
__isaforge_end_170:
__isaforge_begin_171:
	add	a3,a3,t1
__isaforge_end_171:
__isaforge_begin_172:
	srli	t1,a3,15
__isaforge_end_172:
__isaforge_begin_173:
	slli	a3,a3,17
__isaforge_end_173:
__isaforge_begin_174:
	add	a3,a3,t1
__isaforge_end_174:
__isaforge_begin_175:
	lw	t1,44(sp)
__isaforge_end_175:
__isaforge_begin_176:
	li	t4,-1990406144
__isaforge_end_176:
__isaforge_begin_177:
	addi	t4,t4,1982
__isaforge_end_177:
__isaforge_begin_178:
	add	t4,t1,t4
__isaforge_end_178:
__isaforge_begin_179:
	add	a3,a2,a3
__isaforge_end_179:
__isaforge_begin_180:
	add	t4,t4,a4
__isaforge_end_180:
__isaforge_begin_181:
	xor	a4,a5,a2
__isaforge_end_181:
__isaforge_begin_182:
	and	a4,a4,a3
__isaforge_end_182:
__isaforge_begin_183:
	xor	a4,a4,a5
__isaforge_end_183:
__isaforge_begin_184:
	add	a4,a4,t4
__isaforge_end_184:
__isaforge_begin_185:
	lw	s2,48(sp)
__isaforge_end_185:
__isaforge_begin_186:
	srli	t4,a4,10
__isaforge_end_186:
__isaforge_begin_187:
	slli	a4,a4,22
__isaforge_end_187:
__isaforge_begin_188:
	add	a4,a4,t4
__isaforge_end_188:
__isaforge_begin_189:
	li	t4,1804603392
__isaforge_end_189:
__isaforge_begin_190:
	addi	t4,t4,290
__isaforge_end_190:
__isaforge_begin_191:
	add	t4,s2,t4
__isaforge_end_191:
__isaforge_begin_192:
	add	a4,a3,a4
__isaforge_end_192:
__isaforge_begin_193:
	add	t4,t4,a5
__isaforge_end_193:
__isaforge_begin_194:
	xor	a5,a2,a3
__isaforge_end_194:
__isaforge_begin_195:
	and	a5,a5,a4
__isaforge_end_195:
__isaforge_begin_196:
	xor	a5,a5,a2
__isaforge_end_196:
__isaforge_begin_197:
	add	a5,a5,t4
__isaforge_end_197:
__isaforge_begin_198:
	srli	t4,a5,25
__isaforge_end_198:
__isaforge_begin_199:
	slli	a5,a5,7
__isaforge_end_199:
__isaforge_begin_200:
	add	a5,a5,t4
__isaforge_end_200:
__isaforge_begin_201:
	lw	t4,52(sp)
__isaforge_end_201:
__isaforge_begin_202:
	li	t6,-40341504
__isaforge_end_202:
__isaforge_begin_203:
	addi	t6,t6,403
__isaforge_end_203:
__isaforge_begin_204:
	add	t6,t4,t6
__isaforge_end_204:
__isaforge_begin_205:
	add	a5,a4,a5
__isaforge_end_205:
__isaforge_begin_206:
	add	t6,t6,a2
__isaforge_end_206:
__isaforge_begin_207:
	xor	a2,a3,a4
__isaforge_end_207:
__isaforge_begin_208:
	and	a2,a2,a5
__isaforge_end_208:
__isaforge_begin_209:
	xor	a2,a2,a3
__isaforge_end_209:
__isaforge_begin_210:
	add	a2,a2,t6
__isaforge_end_210:
__isaforge_begin_211:
	lw	s4,56(sp)
__isaforge_end_211:
__isaforge_begin_212:
	srli	t6,a2,20
__isaforge_end_212:
__isaforge_begin_213:
	slli	a2,a2,12
__isaforge_end_213:
__isaforge_begin_214:
	add	a2,a2,t6
__isaforge_end_214:
__isaforge_begin_215:
	li	t6,-1502003200
__isaforge_end_215:
__isaforge_begin_216:
	addi	t6,t6,910
__isaforge_end_216:
__isaforge_begin_217:
	add	t6,s4,t6
__isaforge_end_217:
__isaforge_begin_218:
	add	a2,a5,a2
__isaforge_end_218:
__isaforge_begin_219:
	add	t6,t6,a3
__isaforge_end_219:
__isaforge_begin_220:
	xor	a3,a4,a5
__isaforge_end_220:
__isaforge_begin_221:
	and	a3,a3,a2
__isaforge_end_221:
__isaforge_begin_222:
	xor	a3,a3,a4
__isaforge_end_222:
__isaforge_begin_223:
	add	a3,a3,t6
__isaforge_end_223:
__isaforge_begin_224:
	srli	t6,a3,15
__isaforge_end_224:
__isaforge_begin_225:
	slli	a3,a3,17
__isaforge_end_225:
__isaforge_begin_226:
	add	a3,a3,t6
__isaforge_end_226:
__isaforge_begin_227:
	lw	t6,60(sp)
__isaforge_end_227:
__isaforge_begin_228:
	li	s9,1236537344
__isaforge_end_228:
__isaforge_begin_229:
	addi	s9,s9,-2015
__isaforge_end_229:
__isaforge_begin_230:
	add	s9,t6,s9
__isaforge_end_230:
__isaforge_begin_231:
	add	a3,a2,a3
__isaforge_end_231:
__isaforge_begin_232:
	add	s9,s9,a4
__isaforge_end_232:
__isaforge_begin_233:
	xor	a4,a5,a2
__isaforge_end_233:
__isaforge_begin_234:
	and	a4,a4,a3
__isaforge_end_234:
__isaforge_begin_235:
	xor	a4,a4,a5
__isaforge_end_235:
__isaforge_begin_236:
	add	a4,a4,s9
__isaforge_end_236:
__isaforge_begin_237:
	srli	s9,a4,10
__isaforge_end_237:
__isaforge_begin_238:
	slli	a4,a4,22
__isaforge_end_238:
__isaforge_begin_239:
	add	a4,a4,s9
__isaforge_end_239:
__isaforge_begin_240:
	li	s9,-165797888
__isaforge_end_240:
__isaforge_begin_241:
	addi	s9,s9,1378
__isaforge_end_241:
__isaforge_begin_242:
	add	a4,a3,a4
__isaforge_end_242:
__isaforge_begin_243:
	add	s9,t2,s9
__isaforge_end_243:
__isaforge_begin_244:
	add	s9,s9,a5
__isaforge_end_244:
__isaforge_begin_245:
	xor	a5,a3,a4
__isaforge_end_245:
__isaforge_begin_246:
	and	a5,a5,a2
__isaforge_end_246:
__isaforge_begin_247:
	xor	a5,a5,a3
__isaforge_end_247:
__isaforge_begin_248:
	add	a5,a5,s9
__isaforge_end_248:
__isaforge_begin_249:
	srli	s9,a5,27
__isaforge_end_249:
__isaforge_begin_250:
	slli	a5,a5,5
__isaforge_end_250:
__isaforge_begin_251:
	add	a5,a5,s9
__isaforge_end_251:
__isaforge_begin_252:
	li	s9,-1069502464
__isaforge_end_252:
__isaforge_begin_253:
	addi	s9,s9,832
__isaforge_end_253:
__isaforge_begin_254:
	add	a5,a4,a5
__isaforge_end_254:
__isaforge_begin_255:
	add	s9,t5,s9
__isaforge_end_255:
__isaforge_begin_256:
	add	s9,s9,a2
__isaforge_end_256:
__isaforge_begin_257:
	xor	a2,a4,a5
__isaforge_end_257:
__isaforge_begin_258:
	and	a2,a2,a3
__isaforge_end_258:
__isaforge_begin_259:
	xor	a2,a2,a4
__isaforge_end_259:
__isaforge_begin_260:
	add	a2,a2,s9
__isaforge_end_260:
__isaforge_begin_261:
	srli	s9,a2,23
__isaforge_end_261:
__isaforge_begin_262:
	slli	a2,a2,9
__isaforge_end_262:
__isaforge_begin_263:
	add	a2,a2,s9
__isaforge_end_263:
__isaforge_begin_264:
	li	s9,643719168
__isaforge_end_264:
__isaforge_begin_265:
	addi	s9,s9,-1455
__isaforge_end_265:
__isaforge_begin_266:
	add	a2,a5,a2
__isaforge_end_266:
__isaforge_begin_267:
	add	s9,t1,s9
__isaforge_end_267:
__isaforge_begin_268:
	add	s9,s9,a3
__isaforge_end_268:
__isaforge_begin_269:
	xor	a3,a5,a2
__isaforge_end_269:
__isaforge_begin_270:
	and	a3,a3,a4
__isaforge_end_270:
__isaforge_begin_271:
	xor	a3,a3,a5
__isaforge_end_271:
__isaforge_begin_272:
	add	a3,a3,s9
__isaforge_end_272:
__isaforge_begin_273:
	srli	s9,a3,18
__isaforge_end_273:
__isaforge_begin_274:
	slli	a3,a3,14
__isaforge_end_274:
__isaforge_begin_275:
	add	a3,a3,s9
__isaforge_end_275:
__isaforge_begin_276:
	li	s9,-373899264
__isaforge_end_276:
__isaforge_begin_277:
	addi	s9,s9,1962
__isaforge_end_277:
__isaforge_begin_278:
	add	a3,a2,a3
__isaforge_end_278:
__isaforge_begin_279:
	add	s9,s6,s9
__isaforge_end_279:
__isaforge_begin_280:
	add	s9,s9,a4
__isaforge_end_280:
__isaforge_begin_281:
	xor	a4,a2,a3
__isaforge_end_281:
__isaforge_begin_282:
	and	a4,a4,a5
__isaforge_end_282:
__isaforge_begin_283:
	xor	a4,a4,a2
__isaforge_end_283:
__isaforge_begin_284:
	add	a4,a4,s9
__isaforge_end_284:
__isaforge_begin_285:
	srli	s9,a4,12
__isaforge_end_285:
__isaforge_begin_286:
	slli	a4,a4,20
__isaforge_end_286:
__isaforge_begin_287:
	add	a4,a4,s9
__isaforge_end_287:
__isaforge_begin_288:
	li	s9,-701558784
__isaforge_end_288:
__isaforge_begin_289:
	addi	s9,s9,93
__isaforge_end_289:
__isaforge_begin_290:
	add	a4,a3,a4
__isaforge_end_290:
__isaforge_begin_291:
	add	s9,s3,s9
__isaforge_end_291:
__isaforge_begin_292:
	add	s9,s9,a5
__isaforge_end_292:
__isaforge_begin_293:
	xor	a5,a3,a4
__isaforge_end_293:
__isaforge_begin_294:
	and	a5,a5,a2
__isaforge_end_294:
__isaforge_begin_295:
	xor	a5,a5,a3
__isaforge_end_295:
__isaforge_begin_296:
	add	a5,a5,s9
__isaforge_end_296:
__isaforge_begin_297:
	srli	s9,a5,27
__isaforge_end_297:
__isaforge_begin_298:
	slli	a5,a5,5
__isaforge_end_298:
__isaforge_begin_299:
	add	a5,a5,s9
__isaforge_end_299:
__isaforge_begin_300:
	li	s9,38014976
__isaforge_end_300:
__isaforge_begin_301:
	addi	s9,s9,1107
__isaforge_end_301:
__isaforge_begin_302:
	add	a5,a4,a5
__isaforge_end_302:
__isaforge_begin_303:
	add	s9,s0,s9
__isaforge_end_303:
__isaforge_begin_304:
	add	s9,s9,a2
__isaforge_end_304:
__isaforge_begin_305:
	xor	a2,a4,a5
__isaforge_end_305:
__isaforge_begin_306:
	and	a2,a2,a3
__isaforge_end_306:
__isaforge_begin_307:
	xor	a2,a2,a4
__isaforge_end_307:
__isaforge_begin_308:
	add	a2,a2,s9
__isaforge_end_308:
__isaforge_begin_309:
	srli	s9,a2,23
__isaforge_end_309:
__isaforge_begin_310:
	slli	a2,a2,9
__isaforge_end_310:
__isaforge_begin_311:
	add	a2,a2,s9
__isaforge_end_311:
__isaforge_begin_312:
	li	s9,-660480000
__isaforge_end_312:
__isaforge_begin_313:
	addi	s9,s9,1665
__isaforge_end_313:
__isaforge_begin_314:
	add	a2,a5,a2
__isaforge_end_314:
__isaforge_begin_315:
	add	s9,t6,s9
__isaforge_end_315:
__isaforge_begin_316:
	add	s9,s9,a3
__isaforge_end_316:
__isaforge_begin_317:
	xor	a3,a5,a2
__isaforge_end_317:
__isaforge_begin_318:
	and	a3,a3,a4
__isaforge_end_318:
__isaforge_begin_319:
	xor	a3,a3,a5
__isaforge_end_319:
__isaforge_begin_320:
	add	a3,a3,s9
__isaforge_end_320:
__isaforge_begin_321:
	srli	s9,a3,18
__isaforge_end_321:
__isaforge_begin_322:
	slli	a3,a3,14
__isaforge_end_322:
__isaforge_begin_323:
	add	a3,a3,s9
__isaforge_end_323:
__isaforge_begin_324:
	li	s9,-405536768
__isaforge_end_324:
__isaforge_begin_325:
	addi	s9,s9,-1080
__isaforge_end_325:
__isaforge_begin_326:
	add	a3,a2,a3
__isaforge_end_326:
__isaforge_begin_327:
	add	s9,t3,s9
__isaforge_end_327:
__isaforge_begin_328:
	add	s9,s9,a4
__isaforge_end_328:
__isaforge_begin_329:
	xor	a4,a2,a3
__isaforge_end_329:
__isaforge_begin_330:
	and	a4,a4,a5
__isaforge_end_330:
__isaforge_begin_331:
	xor	a4,a4,a2
__isaforge_end_331:
__isaforge_begin_332:
	add	a4,a4,s9
__isaforge_end_332:
__isaforge_begin_333:
	srli	s9,a4,12
__isaforge_end_333:
__isaforge_begin_334:
	slli	a4,a4,20
__isaforge_end_334:
__isaforge_begin_335:
	add	a4,a4,s9
__isaforge_end_335:
__isaforge_begin_336:
	li	s9,568446976
__isaforge_end_336:
__isaforge_begin_337:
	addi	s9,s9,-538
__isaforge_end_337:
__isaforge_begin_338:
	add	a4,a3,a4
__isaforge_end_338:
__isaforge_begin_339:
	add	s9,a6,s9
__isaforge_end_339:
__isaforge_begin_340:
	add	s9,s9,a5
__isaforge_end_340:
__isaforge_begin_341:
	xor	a5,a3,a4
__isaforge_end_341:
__isaforge_begin_342:
	and	a5,a5,a2
__isaforge_end_342:
__isaforge_begin_343:
	xor	a5,a5,a3
__isaforge_end_343:
__isaforge_begin_344:
	add	a5,a5,s9
__isaforge_end_344:
__isaforge_begin_345:
	srli	s9,a5,27
__isaforge_end_345:
__isaforge_begin_346:
	slli	a5,a5,5
__isaforge_end_346:
__isaforge_begin_347:
	add	a5,a5,s9
__isaforge_end_347:
__isaforge_begin_348:
	li	s9,-1019805696
__isaforge_end_348:
__isaforge_begin_349:
	addi	s9,s9,2006
__isaforge_end_349:
__isaforge_begin_350:
	add	a5,a4,a5
__isaforge_end_350:
__isaforge_begin_351:
	add	s9,s4,s9
__isaforge_end_351:
__isaforge_begin_352:
	add	s9,s9,a2
__isaforge_end_352:
__isaforge_begin_353:
	xor	a2,a4,a5
__isaforge_end_353:
__isaforge_begin_354:
	and	a2,a2,a3
__isaforge_end_354:
__isaforge_begin_355:
	xor	a2,a2,a4
__isaforge_end_355:
__isaforge_begin_356:
	add	a2,a2,s9
__isaforge_end_356:
__isaforge_begin_357:
	srli	s9,a2,23
__isaforge_end_357:
__isaforge_begin_358:
	slli	a2,a2,9
__isaforge_end_358:
__isaforge_begin_359:
	add	a2,a2,s9
__isaforge_end_359:
__isaforge_begin_360:
	li	s9,-187363328
__isaforge_end_360:
__isaforge_begin_361:
	addi	s9,s9,-633
__isaforge_end_361:
__isaforge_begin_362:
	add	a2,a5,a2
__isaforge_end_362:
__isaforge_begin_363:
	add	s9,s1,s9
__isaforge_end_363:
__isaforge_begin_364:
	add	s9,s9,a3
__isaforge_end_364:
__isaforge_begin_365:
	xor	a3,a5,a2
__isaforge_end_365:
__isaforge_begin_366:
	and	a3,a3,a4
__isaforge_end_366:
__isaforge_begin_367:
	xor	a3,a3,a5
__isaforge_end_367:
__isaforge_begin_368:
	add	a3,a3,s9
__isaforge_end_368:
__isaforge_begin_369:
	srli	s9,a3,18
__isaforge_end_369:
__isaforge_begin_370:
	slli	a3,a3,14
__isaforge_end_370:
__isaforge_begin_371:
	add	a3,a3,s9
__isaforge_end_371:
__isaforge_begin_372:
	li	s9,1163530240
__isaforge_end_372:
__isaforge_begin_373:
	addi	s9,s9,1261
__isaforge_end_373:
__isaforge_begin_374:
	add	a3,a2,a3
__isaforge_end_374:
__isaforge_begin_375:
	add	s9,t0,s9
__isaforge_end_375:
__isaforge_begin_376:
	add	s9,s9,a4
__isaforge_end_376:
__isaforge_begin_377:
	xor	a4,a2,a3
__isaforge_end_377:
__isaforge_begin_378:
	and	a4,a4,a5
__isaforge_end_378:
__isaforge_begin_379:
	xor	a4,a4,a2
__isaforge_end_379:
__isaforge_begin_380:
	add	a4,a4,s9
__isaforge_end_380:
__isaforge_begin_381:
	srli	s9,a4,12
__isaforge_end_381:
__isaforge_begin_382:
	slli	a4,a4,20
__isaforge_end_382:
__isaforge_begin_383:
	add	a4,a4,s9
__isaforge_end_383:
__isaforge_begin_384:
	li	s9,-1444679680
__isaforge_end_384:
__isaforge_begin_385:
	addi	s9,s9,-1787
__isaforge_end_385:
__isaforge_begin_386:
	add	a4,a3,a4
__isaforge_end_386:
__isaforge_begin_387:
	add	s9,t4,s9
__isaforge_end_387:
__isaforge_begin_388:
	add	s9,s9,a5
__isaforge_end_388:
__isaforge_begin_389:
	xor	a5,a3,a4
__isaforge_end_389:
__isaforge_begin_390:
	and	a5,a5,a2
__isaforge_end_390:
__isaforge_begin_391:
	xor	a5,a5,a3
__isaforge_end_391:
__isaforge_begin_392:
	add	a5,a5,s9
__isaforge_end_392:
__isaforge_begin_393:
	srli	s9,a5,27
__isaforge_end_393:
__isaforge_begin_394:
	slli	a5,a5,5
__isaforge_end_394:
__isaforge_begin_395:
	add	a5,a5,s9
__isaforge_end_395:
__isaforge_begin_396:
	li	s9,-51404800
__isaforge_end_396:
__isaforge_begin_397:
	addi	s9,s9,1016
__isaforge_end_397:
__isaforge_begin_398:
	add	a5,a4,a5
__isaforge_end_398:
__isaforge_begin_399:
	add	s9,a7,s9
__isaforge_end_399:
__isaforge_begin_400:
	add	s9,s9,a2
__isaforge_end_400:
__isaforge_begin_401:
	xor	a2,a4,a5
__isaforge_end_401:
__isaforge_begin_402:
	and	a2,a2,a3
__isaforge_end_402:
__isaforge_begin_403:
	xor	a2,a2,a4
__isaforge_end_403:
__isaforge_begin_404:
	add	a2,a2,s9
__isaforge_end_404:
__isaforge_begin_405:
	srli	s9,a2,23
__isaforge_end_405:
__isaforge_begin_406:
	slli	a2,a2,9
__isaforge_end_406:
__isaforge_begin_407:
	add	a2,a2,s9
__isaforge_end_407:
__isaforge_begin_408:
	li	s9,1735327744
__isaforge_end_408:
__isaforge_begin_409:
	addi	s9,s9,729
__isaforge_end_409:
__isaforge_begin_410:
	add	a2,a5,a2
__isaforge_end_410:
__isaforge_begin_411:
	add	s9,s5,s9
__isaforge_end_411:
__isaforge_begin_412:
	add	s9,s9,a3
__isaforge_end_412:
__isaforge_begin_413:
	xor	a3,a5,a2
__isaforge_end_413:
__isaforge_begin_414:
	and	a3,a3,a4
__isaforge_end_414:
__isaforge_begin_415:
	xor	a3,a3,a5
__isaforge_end_415:
__isaforge_begin_416:
	add	a3,a3,s9
__isaforge_end_416:
__isaforge_begin_417:
	srli	s9,a3,18
__isaforge_end_417:
__isaforge_begin_418:
	slli	a3,a3,14
__isaforge_end_418:
__isaforge_begin_419:
	add	a3,a3,s9
__isaforge_end_419:
__isaforge_begin_420:
	li	s10,-1926606848
__isaforge_end_420:
__isaforge_begin_421:
	add	a3,a2,a3
__isaforge_end_421:
__isaforge_begin_422:
	addi	s10,s10,-886
__isaforge_end_422:
__isaforge_begin_423:
	xor	s9,a2,a3
__isaforge_end_423:
__isaforge_begin_424:
	add	s10,s2,s10
__isaforge_end_424:
__isaforge_begin_425:
	add	s10,s10,a4
__isaforge_end_425:
__isaforge_begin_426:
	and	a4,s9,a5
__isaforge_end_426:
__isaforge_begin_427:
	xor	a4,a4,a2
__isaforge_end_427:
__isaforge_begin_428:
	add	a4,a4,s10
__isaforge_end_428:
__isaforge_begin_429:
	srli	s10,a4,12
__isaforge_end_429:
__isaforge_begin_430:
	slli	a4,a4,20
__isaforge_end_430:
__isaforge_begin_431:
	add	a4,a4,s10
__isaforge_end_431:
__isaforge_begin_432:
	li	s10,-376832
__isaforge_end_432:
__isaforge_begin_433:
	addi	s10,s10,-1726
__isaforge_end_433:
__isaforge_begin_434:
	add	a4,a3,a4
__isaforge_end_434:
__isaforge_begin_435:
	add	s10,s3,s10
__isaforge_end_435:
__isaforge_begin_436:
	add	s10,s10,a5
__isaforge_end_436:
__isaforge_begin_437:
	xor	a5,s9,a4
__isaforge_end_437:
__isaforge_begin_438:
	add	a5,a5,s10
__isaforge_end_438:
__isaforge_begin_439:
	srli	s9,a5,28
__isaforge_end_439:
__isaforge_begin_440:
	slli	a5,a5,4
__isaforge_end_440:
__isaforge_begin_441:
	add	a5,a5,s9
__isaforge_end_441:
__isaforge_begin_442:
	li	s9,-2022576128
__isaforge_end_442:
__isaforge_begin_443:
	addi	s9,s9,1665
__isaforge_end_443:
__isaforge_begin_444:
	add	s9,t0,s9
__isaforge_end_444:
__isaforge_begin_445:
	add	a5,a4,a5
__isaforge_end_445:
__isaforge_begin_446:
	add	a2,s9,a2
__isaforge_end_446:
__isaforge_begin_447:
	xor	s9,a3,a4
__isaforge_end_447:
__isaforge_begin_448:
	xor	s9,s9,a5
__isaforge_end_448:
__isaforge_begin_449:
	add	s9,s9,a2
__isaforge_end_449:
__isaforge_begin_450:
	srli	a2,s9,21
__isaforge_end_450:
__isaforge_begin_451:
	slli	s9,s9,11
__isaforge_end_451:
__isaforge_begin_452:
	add	s9,s9,a2
__isaforge_end_452:
__isaforge_begin_453:
	li	a2,1839030272
__isaforge_end_453:
__isaforge_begin_454:
	addi	a2,a2,290
__isaforge_end_454:
__isaforge_begin_455:
	add	a2,t1,a2
__isaforge_end_455:
__isaforge_begin_456:
	add	s9,a5,s9
__isaforge_end_456:
__isaforge_begin_457:
	add	a3,a2,a3
__isaforge_end_457:
__isaforge_begin_458:
	xor	a2,a4,a5
__isaforge_end_458:
__isaforge_begin_459:
	xor	a2,a2,s9
__isaforge_end_459:
__isaforge_begin_460:
	add	a2,a2,a3
__isaforge_end_460:
__isaforge_begin_461:
	srli	a3,a2,16
__isaforge_end_461:
__isaforge_begin_462:
	slli	a2,a2,16
__isaforge_end_462:
__isaforge_begin_463:
	add	a2,a2,a3
__isaforge_end_463:
__isaforge_begin_464:
	li	a3,-35307520
__isaforge_end_464:
__isaforge_begin_465:
	addi	a3,a3,-2036
__isaforge_end_465:
__isaforge_begin_466:
	add	a3,s4,a3
__isaforge_end_466:
__isaforge_begin_467:
	add	a2,s9,a2
__isaforge_end_467:
__isaforge_begin_468:
	add	a3,a3,a4
__isaforge_end_468:
__isaforge_begin_469:
	xor	a4,a5,s9
__isaforge_end_469:
__isaforge_begin_470:
	xor	a4,a4,a2
__isaforge_end_470:
__isaforge_begin_471:
	add	a4,a4,a3
__isaforge_end_471:
__isaforge_begin_472:
__isaforge_end_472:
__isaforge_begin_473:
__isaforge_end_473:
__isaforge_begin_474:
	.insn r 0x0b, 0, 1, x14, x14, x0
__isaforge_end_474:
__isaforge_begin_475:
	li	a3,-1530990592
__isaforge_end_475:
__isaforge_begin_476:
	addi	a3,a3,-1468
__isaforge_end_476:
__isaforge_begin_477:
	add	a4,a2,a4
__isaforge_end_477:
__isaforge_begin_478:
	add	a3,t2,a3
__isaforge_end_478:
__isaforge_begin_479:
	xor	s10,s9,a2
__isaforge_end_479:
__isaforge_begin_480:
	add	a5,a3,a5
__isaforge_end_480:
__isaforge_begin_481:
	xor	s10,s10,a4
__isaforge_end_481:
__isaforge_begin_482:
	add	s10,s10,a5
__isaforge_end_482:
__isaforge_begin_483:
	srli	a5,s10,28
__isaforge_end_483:
__isaforge_begin_484:
	slli	s10,s10,4
__isaforge_end_484:
__isaforge_begin_485:
	add	s10,s10,a5
__isaforge_end_485:
__isaforge_begin_486:
	li	a5,1272893440
__isaforge_end_486:
__isaforge_begin_487:
	addi	a5,a5,-87
__isaforge_end_487:
__isaforge_begin_488:
	add	s10,a4,s10
__isaforge_end_488:
__isaforge_begin_489:
	xor	a3,a2,a4
__isaforge_end_489:
__isaforge_begin_490:
	add	a5,t3,a5
__isaforge_end_490:
__isaforge_begin_491:
	add	a5,a5,s9
__isaforge_end_491:
__isaforge_begin_492:
	xor	a3,a3,s10
__isaforge_end_492:
__isaforge_begin_493:
	add	a3,a3,a5
__isaforge_end_493:
__isaforge_begin_494:
	srli	a5,a3,21
__isaforge_end_494:
__isaforge_begin_495:
	slli	a3,a3,11
__isaforge_end_495:
__isaforge_begin_496:
	add	a3,a3,a5
__isaforge_end_496:
__isaforge_begin_497:
	li	a5,-155496448
__isaforge_end_497:
__isaforge_begin_498:
	addi	a5,a5,-1184
__isaforge_end_498:
__isaforge_begin_499:
	add	a5,s5,a5
__isaforge_end_499:
__isaforge_begin_500:
	add	a3,s10,a3
__isaforge_end_500:
__isaforge_begin_501:
	add	a2,a5,a2
__isaforge_end_501:
__isaforge_begin_502:
	xor	a5,a4,s10
__isaforge_end_502:
__isaforge_begin_503:
	xor	a5,a5,a3
__isaforge_end_503:
__isaforge_begin_504:
	add	a5,a5,a2
__isaforge_end_504:
__isaforge_begin_505:
	srli	a2,a5,16
__isaforge_end_505:
__isaforge_begin_506:
	slli	a5,a5,16
__isaforge_end_506:
__isaforge_begin_507:
	add	a5,a5,a2
__isaforge_end_507:
__isaforge_begin_508:
	li	a2,-1094729728
__isaforge_end_508:
__isaforge_begin_509:
	addi	a2,a2,-912
__isaforge_end_509:
__isaforge_begin_510:
	add	a2,s0,a2
__isaforge_end_510:
__isaforge_begin_511:
	add	a5,a3,a5
__isaforge_end_511:
__isaforge_begin_512:
	add	a4,a2,a4
__isaforge_end_512:
__isaforge_begin_513:
	xor	a2,s10,a3
__isaforge_end_513:
__isaforge_begin_514:
	xor	a2,a2,a5
__isaforge_end_514:
__isaforge_begin_515:
	add	a2,a2,a4
__isaforge_end_515:
__isaforge_begin_516:
__isaforge_end_516:
__isaforge_begin_517:
	li	s9,681279488
__isaforge_end_517:
__isaforge_begin_518:
__isaforge_end_518:
__isaforge_begin_519:
	.insn r 0x0b, 0, 1, x12, x12, x0
__isaforge_end_519:
__isaforge_begin_520:
	addi	s9,s9,-314
__isaforge_end_520:
__isaforge_begin_521:
	add	a2,a5,a2
__isaforge_end_521:
__isaforge_begin_522:
	xor	a4,a3,a5
__isaforge_end_522:
__isaforge_begin_523:
	add	s9,t4,s9
__isaforge_end_523:
__isaforge_begin_524:
	add	s9,s9,s10
__isaforge_end_524:
__isaforge_begin_525:
	xor	a4,a4,a2
__isaforge_end_525:
__isaforge_begin_526:
	add	a4,a4,s9
__isaforge_end_526:
__isaforge_begin_527:
	srli	s9,a4,28
__isaforge_end_527:
__isaforge_begin_528:
	slli	a4,a4,4
__isaforge_end_528:
__isaforge_begin_529:
	add	a4,a4,s9
__isaforge_end_529:
__isaforge_begin_530:
	li	s9,-358539264
__isaforge_end_530:
__isaforge_begin_531:
	addi	s9,s9,2042
__isaforge_end_531:
__isaforge_begin_532:
	add	s9,s6,s9
__isaforge_end_532:
__isaforge_begin_533:
	add	a4,a2,a4
__isaforge_end_533:
__isaforge_begin_534:
	add	s9,s9,a3
__isaforge_end_534:
__isaforge_begin_535:
	xor	a3,a5,a2
__isaforge_end_535:
__isaforge_begin_536:
	xor	a3,a3,a4
__isaforge_end_536:
__isaforge_begin_537:
	add	a3,a3,s9
__isaforge_end_537:
__isaforge_begin_538:
	srli	s9,a3,21
__isaforge_end_538:
__isaforge_begin_539:
	slli	a3,a3,11
__isaforge_end_539:
__isaforge_begin_540:
	add	a3,a3,s9
__isaforge_end_540:
__isaforge_begin_541:
	li	s9,-722522112
__isaforge_end_541:
__isaforge_begin_542:
	addi	s9,s9,133
__isaforge_end_542:
__isaforge_begin_543:
	add	s9,s1,s9
__isaforge_end_543:
__isaforge_begin_544:
	add	a3,a4,a3
__isaforge_end_544:
__isaforge_begin_545:
	add	a5,s9,a5
__isaforge_end_545:
__isaforge_begin_546:
	xor	s9,a2,a4
__isaforge_end_546:
__isaforge_begin_547:
	xor	s9,s9,a3
__isaforge_end_547:
__isaforge_begin_548:
	add	s9,s9,a5
__isaforge_end_548:
__isaforge_begin_549:
	srli	a5,s9,16
__isaforge_end_549:
__isaforge_begin_550:
	slli	s9,s9,16
__isaforge_end_550:
__isaforge_begin_551:
	add	s9,s9,a5
__isaforge_end_551:
__isaforge_begin_552:
	li	a5,76029952
__isaforge_end_552:
__isaforge_begin_553:
	addi	a5,a5,-763
__isaforge_end_553:
__isaforge_begin_554:
	add	a5,t5,a5
__isaforge_end_554:
__isaforge_begin_555:
	add	s9,a3,s9
__isaforge_end_555:
__isaforge_begin_556:
	add	a2,a5,a2
__isaforge_end_556:
__isaforge_begin_557:
	xor	a5,a4,a3
__isaforge_end_557:
__isaforge_begin_558:
	xor	a5,a5,s9
__isaforge_end_558:
__isaforge_begin_559:
	add	a5,a5,a2
__isaforge_end_559:
__isaforge_begin_560:
__isaforge_end_560:
__isaforge_begin_561:
__isaforge_end_561:
__isaforge_begin_562:
	.insn r 0x0b, 0, 1, x15, x15, x0
__isaforge_end_562:
__isaforge_begin_563:
	li	a2,-640364544
__isaforge_end_563:
__isaforge_begin_564:
	addi	a2,a2,57
__isaforge_end_564:
__isaforge_begin_565:
	add	a2,a6,a2
__isaforge_end_565:
__isaforge_begin_566:
	add	a5,s9,a5
__isaforge_end_566:
__isaforge_begin_567:
	add	a2,a2,a4
__isaforge_end_567:
__isaforge_begin_568:
	xor	a4,a3,s9
__isaforge_end_568:
__isaforge_begin_569:
	xor	a4,a4,a5
__isaforge_end_569:
__isaforge_begin_570:
	add	a4,a4,a2
__isaforge_end_570:
__isaforge_begin_571:
	srli	a2,a4,28
__isaforge_end_571:
__isaforge_begin_572:
	slli	a4,a4,4
__isaforge_end_572:
__isaforge_begin_573:
	add	a4,a4,a2
__isaforge_end_573:
__isaforge_begin_574:
	li	a2,-421814272
__isaforge_end_574:
__isaforge_begin_575:
	addi	a2,a2,-1563
__isaforge_end_575:
__isaforge_begin_576:
	add	a2,s2,a2
__isaforge_end_576:
__isaforge_begin_577:
	add	a4,a5,a4
__isaforge_end_577:
__isaforge_begin_578:
	add	a3,a2,a3
__isaforge_end_578:
__isaforge_begin_579:
	xor	a2,s9,a5
__isaforge_end_579:
__isaforge_begin_580:
	xor	a2,a2,a4
__isaforge_end_580:
__isaforge_begin_581:
	add	a2,a2,a3
__isaforge_end_581:
__isaforge_begin_582:
	srli	a3,a2,21
__isaforge_end_582:
__isaforge_begin_583:
	slli	a2,a2,11
__isaforge_end_583:
__isaforge_begin_584:
	add	a2,a2,a3
__isaforge_end_584:
__isaforge_begin_585:
	li	a3,530743296
__isaforge_end_585:
__isaforge_begin_586:
	addi	a3,a3,-776
__isaforge_end_586:
__isaforge_begin_587:
	add	a3,t6,a3
__isaforge_end_587:
__isaforge_begin_588:
	add	a2,a4,a2
__isaforge_end_588:
__isaforge_begin_589:
	add	s9,a3,s9
__isaforge_end_589:
__isaforge_begin_590:
	xor	a3,a5,a4
__isaforge_end_590:
__isaforge_begin_591:
	xor	a3,a3,a2
__isaforge_end_591:
__isaforge_begin_592:
	add	a3,a3,s9
__isaforge_end_592:
__isaforge_begin_593:
	srli	s9,a3,16
__isaforge_end_593:
__isaforge_begin_594:
	slli	a3,a3,16
__isaforge_end_594:
__isaforge_begin_595:
	add	a3,a3,s9
__isaforge_end_595:
__isaforge_begin_596:
	li	s9,-995340288
__isaforge_end_596:
__isaforge_begin_597:
	addi	s9,s9,1637
__isaforge_end_597:
__isaforge_begin_598:
	add	s9,a7,s9
__isaforge_end_598:
__isaforge_begin_599:
	add	a3,a2,a3
__isaforge_end_599:
__isaforge_begin_600:
	add	s9,s9,a5
__isaforge_end_600:
__isaforge_begin_601:
	xor	a5,a4,a2
__isaforge_end_601:
__isaforge_begin_602:
	xor	a5,a5,a3
__isaforge_end_602:
__isaforge_begin_603:
	add	a5,a5,s9
__isaforge_end_603:
__isaforge_begin_604:
__isaforge_end_604:
__isaforge_begin_605:
__isaforge_end_605:
__isaforge_begin_606:
	.insn r 0x0b, 0, 1, x15, x15, x0
__isaforge_end_606:
__isaforge_begin_607:
	li	s9,-198631424
__isaforge_end_607:
__isaforge_begin_608:
	addi	s9,s9,580
__isaforge_end_608:
__isaforge_begin_609:
	add	s6,s6,s9
__isaforge_end_609:
__isaforge_begin_610:
	add	a5,a3,a5
__isaforge_end_610:
__isaforge_begin_611:
	add	a4,s6,a4
__isaforge_end_611:
__isaforge_begin_612:
	not	s6,a2
__isaforge_end_612:
__isaforge_begin_613:
	or	s6,s6,a5
__isaforge_end_613:
__isaforge_begin_614:
	xor	s6,s6,a3
__isaforge_end_614:
__isaforge_begin_615:
	add	s6,s6,a4
__isaforge_end_615:
__isaforge_begin_616:
	srli	a4,s6,26
__isaforge_end_616:
__isaforge_begin_617:
	slli	s6,s6,6
__isaforge_end_617:
__isaforge_begin_618:
	add	s6,s6,a4
__isaforge_end_618:
__isaforge_begin_619:
	li	a4,1126891520
__isaforge_end_619:
__isaforge_begin_620:
	addi	a4,a4,-105
__isaforge_end_620:
__isaforge_begin_621:
	add	s6,a5,s6
__isaforge_end_621:
__isaforge_begin_622:
	add	s5,s5,a4
__isaforge_end_622:
__isaforge_begin_623:
	not	a4,a3
__isaforge_end_623:
__isaforge_begin_624:
	or	a4,a4,s6
__isaforge_end_624:
__isaforge_begin_625:
	add	s5,s5,a2
__isaforge_end_625:
__isaforge_begin_626:
	xor	a4,a4,a5
__isaforge_end_626:
__isaforge_begin_627:
	add	a4,a4,s5
__isaforge_end_627:
__isaforge_begin_628:
	srli	a2,a4,22
__isaforge_end_628:
__isaforge_begin_629:
	slli	a4,a4,10
__isaforge_end_629:
__isaforge_begin_630:
	add	a4,a4,a2
__isaforge_end_630:
__isaforge_begin_631:
	li	a2,-1416355840
__isaforge_end_631:
__isaforge_begin_632:
	addi	a2,a2,935
__isaforge_end_632:
__isaforge_begin_633:
	add	s4,s4,a2
__isaforge_end_633:
__isaforge_begin_634:
	add	a4,s6,a4
__isaforge_end_634:
__isaforge_begin_635:
	add	s4,s4,a3
__isaforge_end_635:
__isaforge_begin_636:
	not	a3,a5
__isaforge_end_636:
__isaforge_begin_637:
	or	a3,a3,a4
__isaforge_end_637:
__isaforge_begin_638:
	xor	a3,a3,s6
__isaforge_end_638:
__isaforge_begin_639:
	add	a3,a3,s4
__isaforge_end_639:
__isaforge_begin_640:
	srli	a2,a3,17
__isaforge_end_640:
__isaforge_begin_641:
	slli	a3,a3,15
__isaforge_end_641:
__isaforge_begin_642:
	add	a3,a3,a2
__isaforge_end_642:
__isaforge_begin_643:
	li	a2,-57434112
__isaforge_end_643:
__isaforge_begin_644:
	addi	a2,a2,57
__isaforge_end_644:
__isaforge_begin_645:
	add	a3,a4,a3
__isaforge_end_645:
__isaforge_begin_646:
	add	s3,s3,a2
__isaforge_end_646:
__isaforge_begin_647:
	not	a2,s6
__isaforge_end_647:
__isaforge_begin_648:
	or	a2,a2,a3
__isaforge_end_648:
__isaforge_begin_649:
	add	s3,s3,a5
__isaforge_end_649:
__isaforge_begin_650:
	xor	a2,a2,a4
__isaforge_end_650:
__isaforge_begin_651:
	add	a2,a2,s3
__isaforge_end_651:
__isaforge_begin_652:
	srli	a5,a2,11
__isaforge_end_652:
__isaforge_begin_653:
	slli	a2,a2,21
__isaforge_end_653:
__isaforge_begin_654:
	add	a2,a2,a5
__isaforge_end_654:
__isaforge_begin_655:
	li	a5,1700487168
__isaforge_end_655:
__isaforge_begin_656:
	addi	a5,a5,-1597
__isaforge_end_656:
__isaforge_begin_657:
	add	a2,a3,a2
__isaforge_end_657:
__isaforge_begin_658:
	add	s2,s2,a5
__isaforge_end_658:
__isaforge_begin_659:
	not	a5,a4
__isaforge_end_659:
__isaforge_begin_660:
	or	a5,a5,a2
__isaforge_end_660:
__isaforge_begin_661:
	add	s2,s2,s6
__isaforge_end_661:
__isaforge_begin_662:
	xor	a5,a5,a3
__isaforge_end_662:
__isaforge_begin_663:
	add	a5,a5,s2
__isaforge_end_663:
__isaforge_begin_664:
	srli	s2,a5,26
__isaforge_end_664:
__isaforge_begin_665:
	slli	a5,a5,6
__isaforge_end_665:
__isaforge_begin_666:
	add	a5,a5,s2
__isaforge_end_666:
__isaforge_begin_667:
	li	s2,-1894985728
__isaforge_end_667:
__isaforge_begin_668:
	addi	s2,s2,-878
__isaforge_end_668:
__isaforge_begin_669:
	add	s1,s1,s2
__isaforge_end_669:
__isaforge_begin_670:
	add	a5,a2,a5
__isaforge_end_670:
__isaforge_begin_671:
	add	s1,s1,a4
__isaforge_end_671:
__isaforge_begin_672:
	not	a4,a3
__isaforge_end_672:
__isaforge_begin_673:
	or	a4,a4,a5
__isaforge_end_673:
__isaforge_begin_674:
	xor	a4,a4,a2
__isaforge_end_674:
__isaforge_begin_675:
	add	a4,a4,s1
__isaforge_end_675:
__isaforge_begin_676:
	srli	s1,a4,22
__isaforge_end_676:
__isaforge_begin_677:
	slli	a4,a4,10
__isaforge_end_677:
__isaforge_begin_678:
	add	a4,a4,s1
__isaforge_end_678:
__isaforge_begin_679:
	li	s1,-1052672
__isaforge_end_679:
__isaforge_begin_680:
	addi	s1,s1,1149
__isaforge_end_680:
__isaforge_begin_681:
	add	s0,s0,s1
__isaforge_end_681:
__isaforge_begin_682:
	add	a4,a5,a4
__isaforge_end_682:
__isaforge_begin_683:
	add	s0,s0,a3
__isaforge_end_683:
__isaforge_begin_684:
	not	a3,a2
__isaforge_end_684:
__isaforge_begin_685:
	or	a3,a3,a4
__isaforge_end_685:
__isaforge_begin_686:
	xor	a3,a3,a5
__isaforge_end_686:
__isaforge_begin_687:
	add	a3,a3,s0
__isaforge_end_687:
__isaforge_begin_688:
	srli	s0,a3,17
__isaforge_end_688:
__isaforge_begin_689:
	slli	a3,a3,15
__isaforge_end_689:
__isaforge_begin_690:
	add	a3,a3,s0
__isaforge_end_690:
__isaforge_begin_691:
	li	s0,-2054922240
__isaforge_end_691:
__isaforge_begin_692:
	addi	s0,s0,-559
__isaforge_end_692:
__isaforge_begin_693:
	add	t2,t2,s0
__isaforge_end_693:
__isaforge_begin_694:
	add	a3,a4,a3
__isaforge_end_694:
__isaforge_begin_695:
	add	t2,t2,a2
__isaforge_end_695:
__isaforge_begin_696:
	not	a2,a5
__isaforge_end_696:
__isaforge_begin_697:
	or	a2,a2,a3
__isaforge_end_697:
__isaforge_begin_698:
	xor	a2,a2,a4
__isaforge_end_698:
__isaforge_begin_699:
	add	a2,a2,t2
__isaforge_end_699:
__isaforge_begin_700:
	srli	t2,a2,11
__isaforge_end_700:
__isaforge_begin_701:
	slli	a2,a2,21
__isaforge_end_701:
__isaforge_begin_702:
	add	a2,a2,t2
__isaforge_end_702:
__isaforge_begin_703:
	li	t2,1873313792
__isaforge_end_703:
__isaforge_begin_704:
	addi	t2,t2,-433
__isaforge_end_704:
__isaforge_begin_705:
	add	t0,t0,t2
__isaforge_end_705:
__isaforge_begin_706:
	add	a2,a3,a2
__isaforge_end_706:
__isaforge_begin_707:
	add	t0,t0,a5
__isaforge_end_707:
__isaforge_begin_708:
	not	a5,a4
__isaforge_end_708:
__isaforge_begin_709:
	or	a5,a5,a2
__isaforge_end_709:
__isaforge_begin_710:
	xor	a5,a5,a3
__isaforge_end_710:
__isaforge_begin_711:
	add	a5,a5,t0
__isaforge_end_711:
__isaforge_begin_712:
	srli	t0,a5,26
__isaforge_end_712:
__isaforge_begin_713:
	slli	a5,a5,6
__isaforge_end_713:
__isaforge_begin_714:
	add	a5,a5,t0
__isaforge_end_714:
__isaforge_begin_715:
	li	t0,-30613504
__isaforge_end_715:
__isaforge_begin_716:
	addi	t0,t0,1760
__isaforge_end_716:
__isaforge_begin_717:
	add	t6,t6,t0
__isaforge_end_717:
__isaforge_begin_718:
	add	a5,a2,a5
__isaforge_end_718:
__isaforge_begin_719:
	add	t6,t6,a4
__isaforge_end_719:
__isaforge_begin_720:
	not	a4,a3
__isaforge_end_720:
__isaforge_begin_721:
	or	a4,a4,a5
__isaforge_end_721:
__isaforge_begin_722:
	xor	a4,a4,a2
__isaforge_end_722:
__isaforge_begin_723:
	add	a4,a4,t6
__isaforge_end_723:
__isaforge_begin_724:
	srli	t6,a4,22
__isaforge_end_724:
__isaforge_begin_725:
	slli	a4,a4,10
__isaforge_end_725:
__isaforge_begin_726:
	add	a4,a4,t6
__isaforge_end_726:
__isaforge_begin_727:
	li	t6,-1560199168
__isaforge_end_727:
__isaforge_begin_728:
	addi	t6,t6,788
__isaforge_end_728:
__isaforge_begin_729:
	add	t5,t5,t6
__isaforge_end_729:
__isaforge_begin_730:
	add	a4,a5,a4
__isaforge_end_730:
__isaforge_begin_731:
	add	t5,t5,a3
__isaforge_end_731:
__isaforge_begin_732:
	not	a3,a2
__isaforge_end_732:
__isaforge_begin_733:
	or	a3,a3,a4
__isaforge_end_733:
__isaforge_begin_734:
	xor	a3,a3,a5
__isaforge_end_734:
__isaforge_begin_735:
	add	a3,a3,t5
__isaforge_end_735:
__isaforge_begin_736:
	srli	t5,a3,17
__isaforge_end_736:
__isaforge_begin_737:
	slli	a3,a3,15
__isaforge_end_737:
__isaforge_begin_738:
	add	a3,a3,t5
__isaforge_end_738:
__isaforge_begin_739:
	li	t5,1309151232
__isaforge_end_739:
__isaforge_begin_740:
	addi	t5,t5,417
__isaforge_end_740:
__isaforge_begin_741:
	add	t4,t4,t5
__isaforge_end_741:
__isaforge_begin_742:
	add	a3,a4,a3
__isaforge_end_742:
__isaforge_begin_743:
	add	t4,t4,a2
__isaforge_end_743:
__isaforge_begin_744:
	not	a2,a5
__isaforge_end_744:
__isaforge_begin_745:
	or	a2,a2,a3
__isaforge_end_745:
__isaforge_begin_746:
	xor	a2,a2,a4
__isaforge_end_746:
__isaforge_begin_747:
	add	a2,a2,t4
__isaforge_end_747:
__isaforge_begin_748:
	srli	t4,a2,11
__isaforge_end_748:
__isaforge_begin_749:
	slli	a2,a2,21
__isaforge_end_749:
__isaforge_begin_750:
	add	a2,a2,t4
__isaforge_end_750:
__isaforge_begin_751:
	li	t4,-145522688
__isaforge_end_751:
__isaforge_begin_752:
	addi	t4,t4,-382
__isaforge_end_752:
__isaforge_begin_753:
	add	t3,t3,t4
__isaforge_end_753:
__isaforge_begin_754:
	add	a2,a3,a2
__isaforge_end_754:
__isaforge_begin_755:
	add	t3,t3,a5
__isaforge_end_755:
__isaforge_begin_756:
	not	a5,a4
__isaforge_end_756:
__isaforge_begin_757:
	or	a5,a5,a2
__isaforge_end_757:
__isaforge_begin_758:
	xor	a5,a5,a3
__isaforge_end_758:
__isaforge_begin_759:
	add	a5,a5,t3
__isaforge_end_759:
__isaforge_begin_760:
	srli	t3,a5,26
__isaforge_end_760:
__isaforge_begin_761:
	slli	a5,a5,6
__isaforge_end_761:
__isaforge_begin_762:
	add	a5,a5,t3
__isaforge_end_762:
__isaforge_begin_763:
	li	t3,-1120210944
__isaforge_end_763:
__isaforge_begin_764:
	addi	t3,t3,565
__isaforge_end_764:
__isaforge_begin_765:
	add	t1,t1,t3
__isaforge_end_765:
__isaforge_begin_766:
	add	a5,a2,a5
__isaforge_end_766:
__isaforge_begin_767:
	add	t1,t1,a4
__isaforge_end_767:
__isaforge_begin_768:
	not	a4,a3
__isaforge_end_768:
__isaforge_begin_769:
	or	a4,a4,a5
__isaforge_end_769:
__isaforge_begin_770:
	xor	a4,a4,a2
__isaforge_end_770:
__isaforge_begin_771:
	add	a4,a4,t1
__isaforge_end_771:
__isaforge_begin_772:
	srli	t1,a4,22
__isaforge_end_772:
__isaforge_begin_773:
	slli	a4,a4,10
__isaforge_end_773:
__isaforge_begin_774:
	add	a4,a4,t1
__isaforge_end_774:
__isaforge_begin_775:
	li	t1,718786560
__isaforge_end_775:
__isaforge_begin_776:
	addi	t1,t1,699
__isaforge_end_776:
__isaforge_begin_777:
	add	a7,a7,t1
__isaforge_end_777:
__isaforge_begin_778:
	add	a4,a5,a4
__isaforge_end_778:
__isaforge_begin_779:
	add	a7,a7,a3
__isaforge_end_779:
__isaforge_begin_780:
	not	a3,a2
__isaforge_end_780:
__isaforge_begin_781:
	or	a3,a3,a4
__isaforge_end_781:
__isaforge_begin_782:
	xor	a3,a3,a5
__isaforge_end_782:
__isaforge_begin_783:
	add	a3,a3,a7
__isaforge_end_783:
__isaforge_begin_784:
	srli	a7,a3,17
__isaforge_end_784:
__isaforge_begin_785:
	slli	a3,a3,15
__isaforge_end_785:
__isaforge_begin_786:
	add	a3,a3,a7
__isaforge_end_786:
__isaforge_begin_787:
	li	a7,-343486464
__isaforge_end_787:
__isaforge_begin_788:
	addi	a7,a7,913
__isaforge_end_788:
__isaforge_begin_789:
	add	a6,a6,a7
__isaforge_end_789:
__isaforge_begin_790:
	add	a3,a4,a3
__isaforge_end_790:
__isaforge_begin_791:
	add	a6,a6,a2
__isaforge_end_791:
__isaforge_begin_792:
	not	a2,a5
__isaforge_end_792:
__isaforge_begin_793:
	or	a2,a2,a3
__isaforge_end_793:
__isaforge_begin_794:
	xor	a2,a2,a4
__isaforge_end_794:
__isaforge_begin_795:
	add	a2,a2,a6
__isaforge_end_795:
__isaforge_begin_796:
	lw	a6,0(a0)
__isaforge_end_796:
__isaforge_begin_797:
	lw	s0,108(sp)
__isaforge_end_797:
__isaforge_begin_798:
	add	a1,a1,a3
__isaforge_end_798:
__isaforge_begin_799:
	add	a5,a6,a5
__isaforge_end_799:
__isaforge_begin_800:
	sw	a5,0(a0)
__isaforge_end_800:
__isaforge_begin_801:
	srli	a5,a2,11
__isaforge_end_801:
__isaforge_begin_802:
	slli	a2,a2,21
__isaforge_end_802:
__isaforge_begin_803:
	add	a5,a5,a2
__isaforge_end_803:
__isaforge_begin_804:
	add	s7,s7,a3
__isaforge_end_804:
__isaforge_begin_805:
	add	s8,s8,a4
__isaforge_end_805:
__isaforge_begin_806:
	add	a5,a5,a1
__isaforge_end_806:
__isaforge_begin_807:
	lw	s1,104(sp)
__isaforge_end_807:
__isaforge_begin_808:
	lw	s2,100(sp)
__isaforge_end_808:
__isaforge_begin_809:
	lw	s3,96(sp)
__isaforge_end_809:
__isaforge_begin_810:
	lw	s4,92(sp)
__isaforge_end_810:
__isaforge_begin_811:
	lw	s5,88(sp)
__isaforge_end_811:
__isaforge_begin_812:
	lw	s6,84(sp)
__isaforge_end_812:
__isaforge_begin_813:
	sw	s8,12(a0)
__isaforge_end_813:
__isaforge_begin_814:
	sw	a5,4(a0)
__isaforge_end_814:
__isaforge_begin_815:
	sw	s7,8(a0)
__isaforge_end_815:
__isaforge_begin_816:
	lw	s7,80(sp)
__isaforge_end_816:
__isaforge_begin_817:
	lw	s8,76(sp)
__isaforge_end_817:
__isaforge_begin_818:
	lw	s9,72(sp)
__isaforge_end_818:
__isaforge_begin_819:
	lw	s10,68(sp)
__isaforge_end_819:
__isaforge_begin_820:
	addi	sp,sp,112
__isaforge_end_820:
__isaforge_begin_821:
	jr	ra
__isaforge_end_821:
	.size	_nettle_md5_compress, .-_nettle_md5_compress
	.section	.text.initialise_benchmark,"ax",@progbits
	.align	2
	.globl	initialise_benchmark
	.type	initialise_benchmark, @function
initialise_benchmark:
__isaforge_begin_822:
	ret
__isaforge_end_822:
	.size	initialise_benchmark, .-initialise_benchmark
	.section	.text.benchmark,"ax",@progbits
	.align	2
	.globl	benchmark
	.type	benchmark, @function
benchmark:
__isaforge_begin_823:
	addi	sp,sp,-16
__isaforge_end_823:
__isaforge_begin_824:
	sw	s0,8(sp)
__isaforge_end_824:
__isaforge_begin_825:
	lui	a1,%hi(digest_ref)
__isaforge_end_825:
__isaforge_begin_826:
	lui	s0,%hi(digest)
__isaforge_end_826:
__isaforge_begin_827:
	li	a2,16
__isaforge_end_827:
__isaforge_begin_828:
	addi	a1,a1,%lo(digest_ref)
__isaforge_end_828:
__isaforge_begin_829:
	addi	a0,s0,%lo(digest)
__isaforge_end_829:
__isaforge_begin_830:
	sw	ra,12(sp)
__isaforge_end_830:
__isaforge_begin_831:
	call	memcpy
__isaforge_end_831:
__isaforge_begin_832:
	lui	a1,%hi(input)
__isaforge_end_832:
__isaforge_begin_833:
	addi	a0,s0,%lo(digest)
__isaforge_end_833:
__isaforge_begin_834:
	addi	a1,a1,%lo(input)
__isaforge_end_834:
__isaforge_begin_835:
	call	_nettle_md5_compress
__isaforge_end_835:
__isaforge_begin_836:
	lw	ra,12(sp)
__isaforge_end_836:
__isaforge_begin_837:
	lw	s0,8(sp)
__isaforge_end_837:
__isaforge_begin_838:
	li	a0,0
__isaforge_end_838:
__isaforge_begin_839:
	addi	sp,sp,16
__isaforge_end_839:
__isaforge_begin_840:
	jr	ra
__isaforge_end_840:
	.size	benchmark, .-benchmark
	.section	.text.verify_benchmark,"ax",@progbits
	.align	2
	.globl	verify_benchmark
	.type	verify_benchmark, @function
verify_benchmark:
__isaforge_begin_841:
	addi	sp,sp,-32
__isaforge_end_841:
__isaforge_begin_842:
	lui	a1,%hi(.LANCHOR0)
__isaforge_end_842:
__isaforge_begin_843:
	li	a2,16
__isaforge_end_843:
__isaforge_begin_844:
	addi	a1,a1,%lo(.LANCHOR0)
__isaforge_end_844:
__isaforge_begin_845:
	mv	a0,sp
__isaforge_end_845:
__isaforge_begin_846:
	sw	ra,28(sp)
__isaforge_end_846:
__isaforge_begin_847:
	call	memcpy
__isaforge_end_847:
__isaforge_begin_848:
	lui	a0,%hi(digest)
__isaforge_end_848:
__isaforge_begin_849:
	mv	a1,sp
__isaforge_end_849:
__isaforge_begin_850:
	li	a2,16
__isaforge_end_850:
__isaforge_begin_851:
	addi	a0,a0,%lo(digest)
__isaforge_end_851:
__isaforge_begin_852:
	call	memcmp
__isaforge_end_852:
__isaforge_begin_853:
	lw	ra,28(sp)
__isaforge_end_853:
__isaforge_begin_854:
	seqz	a0,a0
__isaforge_end_854:
__isaforge_begin_855:
	addi	sp,sp,32
__isaforge_end_855:
__isaforge_begin_856:
	jr	ra
__isaforge_end_856:
	.size	verify_benchmark, .-verify_benchmark
	.globl	digest
	.section	.bss.digest,"aw",@nobits
	.align	2
	.type	digest, @object
	.size	digest, 16
digest:
	.zero	16
	.section	.rodata.digest_ref,"a"
	.align	2
	.type	digest_ref, @object
	.size	digest_ref, 16
digest_ref:
	.word	1732584193
	.word	-271733879
	.word	-1732584194
	.word	271733878
	.section	.data.input,"aw"
	.align	2
	.type	input, @object
	.size	input, 64
input:
	.base64	"AAECAwQFBgcICQoLDA0ODwABAgMEBQYHCAkKCwwNDg8AAQIDBAUGBwgJCgsMDQ4PAAECAwQFBgcICQoLDA0ODw=="
	.section	.rodata
	.align	2
	.set	.LANCHOR0,. + 0
.LC0:
	.word	-575698923
	.word	558484367
	.word	-1663207939
	.word	346308135
	.ident	"GCC: (xPack GNU RISC-V Embedded GCC arm64) 15.2.0"
	.section	.note.GNU-stack,"",@progbits
