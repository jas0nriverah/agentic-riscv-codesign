.option norvc
.option norelax
.section .text.start
.global _start
_start:
li t0,2779077210
li t1,1520805210
.global probe_0
probe_0:
add t2,t0,t1
li t3,4915124
bne t2,t3,fail
.global probe_1
probe_1:
sub t2,t0,t1
li t3,1258272000
bne t2,t3,fail
.global probe_2
probe_2:
and t2,t0,t1
li t3,10813530
bne t2,t3,fail
.global probe_3
probe_3:
or t2,t0,t1
li t3,4289068890
bne t2,t3,fail
.global probe_4
probe_4:
xor t2,t0,t1
li t3,4278255360
bne t2,t3,fail
.global probe_5
probe_5:
slt t2,t0,t1
li t3,1
bne t2,t3,fail
.global probe_6
probe_6:
sltu t2,t0,t1
li t3,0
bne t2,t3,fail
.global probe_7
probe_7:
addi t2,t0,-3
li t3,2779077207
bne t2,t3,fail
.global probe_8
probe_8:
andi t2,t0,255
li t3,90
bne t2,t3,fail
.global probe_9
probe_9:
ori t2,t0,255
li t3,2779077375
bne t2,t3,fail
.global probe_10
probe_10:
xori t2,t0,255
li t3,2779077285
bne t2,t3,fail
.global probe_11
probe_11:
slti t2,t0,-3
li t3,1
bne t2,t3,fail
.global probe_12
probe_12:
sltiu t2,t0,-3
li t3,1
bne t2,t3,fail
.global probe_13
probe_13:
lui t2,0x12345
li t3,305418240
bne t2,t3,fail
.global probe_14
probe_14:
slli t2,t0,0
li t3,2779077210
bne t2,t3,fail
.global probe_15
probe_15:
slli t2,t0,1
li t3,1263187124
bne t2,t3,fail
.global probe_16
probe_16:
slli t2,t0,2
li t3,2526374248
bne t2,t3,fail
.global probe_17
probe_17:
slli t2,t0,3
li t3,757781200
bne t2,t3,fail
.global probe_18
probe_18:
slli t2,t0,4
li t3,1515562400
bne t2,t3,fail
.global probe_19
probe_19:
slli t2,t0,5
li t3,3031124800
bne t2,t3,fail
.global probe_20
probe_20:
slli t2,t0,6
li t3,1767282304
bne t2,t3,fail
.global probe_21
probe_21:
slli t2,t0,7
li t3,3534564608
bne t2,t3,fail
.global probe_22
probe_22:
slli t2,t0,8
li t3,2774161920
bne t2,t3,fail
.global probe_23
probe_23:
slli t2,t0,9
li t3,1253356544
bne t2,t3,fail
.global probe_24
probe_24:
slli t2,t0,10
li t3,2506713088
bne t2,t3,fail
.global probe_25
probe_25:
slli t2,t0,11
li t3,718458880
bne t2,t3,fail
.global probe_26
probe_26:
slli t2,t0,12
li t3,1436917760
bne t2,t3,fail
.global probe_27
probe_27:
slli t2,t0,13
li t3,2873835520
bne t2,t3,fail
.global probe_28
probe_28:
slli t2,t0,14
li t3,1452703744
bne t2,t3,fail
.global probe_29
probe_29:
slli t2,t0,15
li t3,2905407488
bne t2,t3,fail
.global probe_30
probe_30:
slli t2,t0,16
li t3,1515847680
bne t2,t3,fail
.global probe_31
probe_31:
slli t2,t0,17
li t3,3031695360
bne t2,t3,fail
.global probe_32
probe_32:
slli t2,t0,18
li t3,1768423424
bne t2,t3,fail
.global probe_33
probe_33:
slli t2,t0,19
li t3,3536846848
bne t2,t3,fail
.global probe_34
probe_34:
slli t2,t0,20
li t3,2778726400
bne t2,t3,fail
.global probe_35
probe_35:
slli t2,t0,21
li t3,1262485504
bne t2,t3,fail
.global probe_36
probe_36:
slli t2,t0,22
li t3,2524971008
bne t2,t3,fail
.global probe_37
probe_37:
slli t2,t0,23
li t3,754974720
bne t2,t3,fail
.global probe_38
probe_38:
slli t2,t0,24
li t3,1509949440
bne t2,t3,fail
.global probe_39
probe_39:
slli t2,t0,25
li t3,3019898880
bne t2,t3,fail
.global probe_40
probe_40:
slli t2,t0,26
li t3,1744830464
bne t2,t3,fail
.global probe_41
probe_41:
slli t2,t0,27
li t3,3489660928
bne t2,t3,fail
.global probe_42
probe_42:
slli t2,t0,28
li t3,2684354560
bne t2,t3,fail
.global probe_43
probe_43:
slli t2,t0,29
li t3,1073741824
bne t2,t3,fail
.global probe_44
probe_44:
slli t2,t0,30
li t3,2147483648
bne t2,t3,fail
.global probe_45
probe_45:
slli t2,t0,31
li t3,0
bne t2,t3,fail
.global probe_46
probe_46:
srli t2,t0,0
li t3,2779077210
bne t2,t3,fail
.global probe_47
probe_47:
srli t2,t0,1
li t3,1389538605
bne t2,t3,fail
.global probe_48
probe_48:
srli t2,t0,2
li t3,694769302
bne t2,t3,fail
.global probe_49
probe_49:
srli t2,t0,3
li t3,347384651
bne t2,t3,fail
.global probe_50
probe_50:
srli t2,t0,4
li t3,173692325
bne t2,t3,fail
.global probe_51
probe_51:
srli t2,t0,5
li t3,86846162
bne t2,t3,fail
.global probe_52
probe_52:
srli t2,t0,6
li t3,43423081
bne t2,t3,fail
.global probe_53
probe_53:
srli t2,t0,7
li t3,21711540
bne t2,t3,fail
.global probe_54
probe_54:
srli t2,t0,8
li t3,10855770
bne t2,t3,fail
.global probe_55
probe_55:
srli t2,t0,9
li t3,5427885
bne t2,t3,fail
.global probe_56
probe_56:
srli t2,t0,10
li t3,2713942
bne t2,t3,fail
.global probe_57
probe_57:
srli t2,t0,11
li t3,1356971
bne t2,t3,fail
.global probe_58
probe_58:
srli t2,t0,12
li t3,678485
bne t2,t3,fail
.global probe_59
probe_59:
srli t2,t0,13
li t3,339242
bne t2,t3,fail
.global probe_60
probe_60:
srli t2,t0,14
li t3,169621
bne t2,t3,fail
.global probe_61
probe_61:
srli t2,t0,15
li t3,84810
bne t2,t3,fail
.global probe_62
probe_62:
srli t2,t0,16
li t3,42405
bne t2,t3,fail
.global probe_63
probe_63:
srli t2,t0,17
li t3,21202
bne t2,t3,fail
.global probe_64
probe_64:
srli t2,t0,18
li t3,10601
bne t2,t3,fail
.global probe_65
probe_65:
srli t2,t0,19
li t3,5300
bne t2,t3,fail
.global probe_66
probe_66:
srli t2,t0,20
li t3,2650
bne t2,t3,fail
.global probe_67
probe_67:
srli t2,t0,21
li t3,1325
bne t2,t3,fail
.global probe_68
probe_68:
srli t2,t0,22
li t3,662
bne t2,t3,fail
.global probe_69
probe_69:
srli t2,t0,23
li t3,331
bne t2,t3,fail
.global probe_70
probe_70:
srli t2,t0,24
li t3,165
bne t2,t3,fail
.global probe_71
probe_71:
srli t2,t0,25
li t3,82
bne t2,t3,fail
.global probe_72
probe_72:
srli t2,t0,26
li t3,41
bne t2,t3,fail
.global probe_73
probe_73:
srli t2,t0,27
li t3,20
bne t2,t3,fail
.global probe_74
probe_74:
srli t2,t0,28
li t3,10
bne t2,t3,fail
.global probe_75
probe_75:
srli t2,t0,29
li t3,5
bne t2,t3,fail
.global probe_76
probe_76:
srli t2,t0,30
li t3,2
bne t2,t3,fail
.global probe_77
probe_77:
srli t2,t0,31
li t3,1
bne t2,t3,fail
.global probe_78
probe_78:
srai t2,t0,0
li t3,2779077210
bne t2,t3,fail
.global probe_79
probe_79:
srai t2,t0,1
li t3,3537022253
bne t2,t3,fail
.global probe_80
probe_80:
srai t2,t0,2
li t3,3915994774
bne t2,t3,fail
.global probe_81
probe_81:
srai t2,t0,3
li t3,4105481035
bne t2,t3,fail
.global probe_82
probe_82:
srai t2,t0,4
li t3,4200224165
bne t2,t3,fail
.global probe_83
probe_83:
srai t2,t0,5
li t3,4247595730
bne t2,t3,fail
.global probe_84
probe_84:
srai t2,t0,6
li t3,4271281513
bne t2,t3,fail
.global probe_85
probe_85:
srai t2,t0,7
li t3,4283124404
bne t2,t3,fail
.global probe_86
probe_86:
srai t2,t0,8
li t3,4289045850
bne t2,t3,fail
.global probe_87
probe_87:
srai t2,t0,9
li t3,4292006573
bne t2,t3,fail
.global probe_88
probe_88:
srai t2,t0,10
li t3,4293486934
bne t2,t3,fail
.global probe_89
probe_89:
srai t2,t0,11
li t3,4294227115
bne t2,t3,fail
.global probe_90
probe_90:
srai t2,t0,12
li t3,4294597205
bne t2,t3,fail
.global probe_91
probe_91:
srai t2,t0,13
li t3,4294782250
bne t2,t3,fail
.global probe_92
probe_92:
srai t2,t0,14
li t3,4294874773
bne t2,t3,fail
.global probe_93
probe_93:
srai t2,t0,15
li t3,4294921034
bne t2,t3,fail
.global probe_94
probe_94:
srai t2,t0,16
li t3,4294944165
bne t2,t3,fail
.global probe_95
probe_95:
srai t2,t0,17
li t3,4294955730
bne t2,t3,fail
.global probe_96
probe_96:
srai t2,t0,18
li t3,4294961513
bne t2,t3,fail
.global probe_97
probe_97:
srai t2,t0,19
li t3,4294964404
bne t2,t3,fail
.global probe_98
probe_98:
srai t2,t0,20
li t3,4294965850
bne t2,t3,fail
.global probe_99
probe_99:
srai t2,t0,21
li t3,4294966573
bne t2,t3,fail
.global probe_100
probe_100:
srai t2,t0,22
li t3,4294966934
bne t2,t3,fail
.global probe_101
probe_101:
srai t2,t0,23
li t3,4294967115
bne t2,t3,fail
.global probe_102
probe_102:
srai t2,t0,24
li t3,4294967205
bne t2,t3,fail
.global probe_103
probe_103:
srai t2,t0,25
li t3,4294967250
bne t2,t3,fail
.global probe_104
probe_104:
srai t2,t0,26
li t3,4294967273
bne t2,t3,fail
.global probe_105
probe_105:
srai t2,t0,27
li t3,4294967284
bne t2,t3,fail
.global probe_106
probe_106:
srai t2,t0,28
li t3,4294967290
bne t2,t3,fail
.global probe_107
probe_107:
srai t2,t0,29
li t3,4294967293
bne t2,t3,fail
.global probe_108
probe_108:
srai t2,t0,30
li t3,4294967294
bne t2,t3,fail
.global probe_109
probe_109:
srai t2,t0,31
li t3,4294967295
bne t2,t3,fail
li t0,2147483647
li t1,4294967295
.global probe_110
probe_110:
add t2,t0,t1
li t3,2147483646
bne t2,t3,fail
.global probe_111
probe_111:
sub t2,t0,t1
li t3,2147483648
bne t2,t3,fail
.global probe_112
probe_112:
and t2,t0,t1
li t3,2147483647
bne t2,t3,fail
.global probe_113
probe_113:
or t2,t0,t1
li t3,4294967295
bne t2,t3,fail
.global probe_114
probe_114:
xor t2,t0,t1
li t3,2147483648
bne t2,t3,fail
.global probe_115
probe_115:
slt t2,t0,t1
li t3,0
bne t2,t3,fail
.global probe_116
probe_116:
sltu t2,t0,t1
li t3,1
bne t2,t3,fail
.global probe_117
probe_117:
addi t2,t0,-3
li t3,2147483644
bne t2,t3,fail
.global probe_118
probe_118:
andi t2,t0,255
li t3,255
bne t2,t3,fail
.global probe_119
probe_119:
ori t2,t0,255
li t3,2147483647
bne t2,t3,fail
.global probe_120
probe_120:
xori t2,t0,255
li t3,2147483392
bne t2,t3,fail
.global probe_121
probe_121:
slti t2,t0,-3
li t3,0
bne t2,t3,fail
.global probe_122
probe_122:
sltiu t2,t0,-3
li t3,1
bne t2,t3,fail
.global probe_123
probe_123:
lui t2,0x12345
li t3,305418240
bne t2,t3,fail
.global probe_124
probe_124:
slli t2,t0,0
li t3,2147483647
bne t2,t3,fail
.global probe_125
probe_125:
slli t2,t0,1
li t3,4294967294
bne t2,t3,fail
.global probe_126
probe_126:
slli t2,t0,2
li t3,4294967292
bne t2,t3,fail
.global probe_127
probe_127:
slli t2,t0,3
li t3,4294967288
bne t2,t3,fail
.global probe_128
probe_128:
slli t2,t0,4
li t3,4294967280
bne t2,t3,fail
.global probe_129
probe_129:
slli t2,t0,5
li t3,4294967264
bne t2,t3,fail
.global probe_130
probe_130:
slli t2,t0,6
li t3,4294967232
bne t2,t3,fail
.global probe_131
probe_131:
slli t2,t0,7
li t3,4294967168
bne t2,t3,fail
.global probe_132
probe_132:
slli t2,t0,8
li t3,4294967040
bne t2,t3,fail
.global probe_133
probe_133:
slli t2,t0,9
li t3,4294966784
bne t2,t3,fail
.global probe_134
probe_134:
slli t2,t0,10
li t3,4294966272
bne t2,t3,fail
.global probe_135
probe_135:
slli t2,t0,11
li t3,4294965248
bne t2,t3,fail
.global probe_136
probe_136:
slli t2,t0,12
li t3,4294963200
bne t2,t3,fail
.global probe_137
probe_137:
slli t2,t0,13
li t3,4294959104
bne t2,t3,fail
.global probe_138
probe_138:
slli t2,t0,14
li t3,4294950912
bne t2,t3,fail
.global probe_139
probe_139:
slli t2,t0,15
li t3,4294934528
bne t2,t3,fail
.global probe_140
probe_140:
slli t2,t0,16
li t3,4294901760
bne t2,t3,fail
.global probe_141
probe_141:
slli t2,t0,17
li t3,4294836224
bne t2,t3,fail
.global probe_142
probe_142:
slli t2,t0,18
li t3,4294705152
bne t2,t3,fail
.global probe_143
probe_143:
slli t2,t0,19
li t3,4294443008
bne t2,t3,fail
.global probe_144
probe_144:
slli t2,t0,20
li t3,4293918720
bne t2,t3,fail
.global probe_145
probe_145:
slli t2,t0,21
li t3,4292870144
bne t2,t3,fail
.global probe_146
probe_146:
slli t2,t0,22
li t3,4290772992
bne t2,t3,fail
.global probe_147
probe_147:
slli t2,t0,23
li t3,4286578688
bne t2,t3,fail
.global probe_148
probe_148:
slli t2,t0,24
li t3,4278190080
bne t2,t3,fail
.global probe_149
probe_149:
slli t2,t0,25
li t3,4261412864
bne t2,t3,fail
.global probe_150
probe_150:
slli t2,t0,26
li t3,4227858432
bne t2,t3,fail
.global probe_151
probe_151:
slli t2,t0,27
li t3,4160749568
bne t2,t3,fail
.global probe_152
probe_152:
slli t2,t0,28
li t3,4026531840
bne t2,t3,fail
.global probe_153
probe_153:
slli t2,t0,29
li t3,3758096384
bne t2,t3,fail
.global probe_154
probe_154:
slli t2,t0,30
li t3,3221225472
bne t2,t3,fail
.global probe_155
probe_155:
slli t2,t0,31
li t3,2147483648
bne t2,t3,fail
.global probe_156
probe_156:
srli t2,t0,0
li t3,2147483647
bne t2,t3,fail
.global probe_157
probe_157:
srli t2,t0,1
li t3,1073741823
bne t2,t3,fail
.global probe_158
probe_158:
srli t2,t0,2
li t3,536870911
bne t2,t3,fail
.global probe_159
probe_159:
srli t2,t0,3
li t3,268435455
bne t2,t3,fail
.global probe_160
probe_160:
srli t2,t0,4
li t3,134217727
bne t2,t3,fail
.global probe_161
probe_161:
srli t2,t0,5
li t3,67108863
bne t2,t3,fail
.global probe_162
probe_162:
srli t2,t0,6
li t3,33554431
bne t2,t3,fail
.global probe_163
probe_163:
srli t2,t0,7
li t3,16777215
bne t2,t3,fail
.global probe_164
probe_164:
srli t2,t0,8
li t3,8388607
bne t2,t3,fail
.global probe_165
probe_165:
srli t2,t0,9
li t3,4194303
bne t2,t3,fail
.global probe_166
probe_166:
srli t2,t0,10
li t3,2097151
bne t2,t3,fail
.global probe_167
probe_167:
srli t2,t0,11
li t3,1048575
bne t2,t3,fail
.global probe_168
probe_168:
srli t2,t0,12
li t3,524287
bne t2,t3,fail
.global probe_169
probe_169:
srli t2,t0,13
li t3,262143
bne t2,t3,fail
.global probe_170
probe_170:
srli t2,t0,14
li t3,131071
bne t2,t3,fail
.global probe_171
probe_171:
srli t2,t0,15
li t3,65535
bne t2,t3,fail
.global probe_172
probe_172:
srli t2,t0,16
li t3,32767
bne t2,t3,fail
.global probe_173
probe_173:
srli t2,t0,17
li t3,16383
bne t2,t3,fail
.global probe_174
probe_174:
srli t2,t0,18
li t3,8191
bne t2,t3,fail
.global probe_175
probe_175:
srli t2,t0,19
li t3,4095
bne t2,t3,fail
.global probe_176
probe_176:
srli t2,t0,20
li t3,2047
bne t2,t3,fail
.global probe_177
probe_177:
srli t2,t0,21
li t3,1023
bne t2,t3,fail
.global probe_178
probe_178:
srli t2,t0,22
li t3,511
bne t2,t3,fail
.global probe_179
probe_179:
srli t2,t0,23
li t3,255
bne t2,t3,fail
.global probe_180
probe_180:
srli t2,t0,24
li t3,127
bne t2,t3,fail
.global probe_181
probe_181:
srli t2,t0,25
li t3,63
bne t2,t3,fail
.global probe_182
probe_182:
srli t2,t0,26
li t3,31
bne t2,t3,fail
.global probe_183
probe_183:
srli t2,t0,27
li t3,15
bne t2,t3,fail
.global probe_184
probe_184:
srli t2,t0,28
li t3,7
bne t2,t3,fail
.global probe_185
probe_185:
srli t2,t0,29
li t3,3
bne t2,t3,fail
.global probe_186
probe_186:
srli t2,t0,30
li t3,1
bne t2,t3,fail
.global probe_187
probe_187:
srli t2,t0,31
li t3,0
bne t2,t3,fail
.global probe_188
probe_188:
srai t2,t0,0
li t3,2147483647
bne t2,t3,fail
.global probe_189
probe_189:
srai t2,t0,1
li t3,1073741823
bne t2,t3,fail
.global probe_190
probe_190:
srai t2,t0,2
li t3,536870911
bne t2,t3,fail
.global probe_191
probe_191:
srai t2,t0,3
li t3,268435455
bne t2,t3,fail
.global probe_192
probe_192:
srai t2,t0,4
li t3,134217727
bne t2,t3,fail
.global probe_193
probe_193:
srai t2,t0,5
li t3,67108863
bne t2,t3,fail
.global probe_194
probe_194:
srai t2,t0,6
li t3,33554431
bne t2,t3,fail
.global probe_195
probe_195:
srai t2,t0,7
li t3,16777215
bne t2,t3,fail
.global probe_196
probe_196:
srai t2,t0,8
li t3,8388607
bne t2,t3,fail
.global probe_197
probe_197:
srai t2,t0,9
li t3,4194303
bne t2,t3,fail
.global probe_198
probe_198:
srai t2,t0,10
li t3,2097151
bne t2,t3,fail
.global probe_199
probe_199:
srai t2,t0,11
li t3,1048575
bne t2,t3,fail
.global probe_200
probe_200:
srai t2,t0,12
li t3,524287
bne t2,t3,fail
.global probe_201
probe_201:
srai t2,t0,13
li t3,262143
bne t2,t3,fail
.global probe_202
probe_202:
srai t2,t0,14
li t3,131071
bne t2,t3,fail
.global probe_203
probe_203:
srai t2,t0,15
li t3,65535
bne t2,t3,fail
.global probe_204
probe_204:
srai t2,t0,16
li t3,32767
bne t2,t3,fail
.global probe_205
probe_205:
srai t2,t0,17
li t3,16383
bne t2,t3,fail
.global probe_206
probe_206:
srai t2,t0,18
li t3,8191
bne t2,t3,fail
.global probe_207
probe_207:
srai t2,t0,19
li t3,4095
bne t2,t3,fail
.global probe_208
probe_208:
srai t2,t0,20
li t3,2047
bne t2,t3,fail
.global probe_209
probe_209:
srai t2,t0,21
li t3,1023
bne t2,t3,fail
.global probe_210
probe_210:
srai t2,t0,22
li t3,511
bne t2,t3,fail
.global probe_211
probe_211:
srai t2,t0,23
li t3,255
bne t2,t3,fail
.global probe_212
probe_212:
srai t2,t0,24
li t3,127
bne t2,t3,fail
.global probe_213
probe_213:
srai t2,t0,25
li t3,63
bne t2,t3,fail
.global probe_214
probe_214:
srai t2,t0,26
li t3,31
bne t2,t3,fail
.global probe_215
probe_215:
srai t2,t0,27
li t3,15
bne t2,t3,fail
.global probe_216
probe_216:
srai t2,t0,28
li t3,7
bne t2,t3,fail
.global probe_217
probe_217:
srai t2,t0,29
li t3,3
bne t2,t3,fail
.global probe_218
probe_218:
srai t2,t0,30
li t3,1
bne t2,t3,fail
.global probe_219
probe_219:
srai t2,t0,31
li t3,0
bne t2,t3,fail
li t0,2779077210
li t1,1520805210
.global probe_220
probe_220:
.insn r 0x0b,0,1,t2,t0,t1
li t3,4915124
bne t2,t3,fail
li t0,2147483647
li t1,4294967295
.global probe_221
probe_221:
.insn r 0x0b,0,1,t2,t0,t1
li t3,2147483646
bne t2,t3,fail
li s0,0x10000000
li t0,0x49534146
sw t0,0(s0)
li t0,222
sw t0,0(s0)
li t0,0x600d600d
sw t0,4(s0)
1: j 1b
fail:
li s0,0x10000000
li t0,0xdead0003
sw t0,4(s0)
2: j 2b
