(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1159 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) (_ bv3328 32))))
(let ((?x84 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x493 (bvshl (bvadd independent_opaque_0 (_ bv832 32)) ?x84)))
(and (distinct ?x493 ?x1159) true)))))
(check-sat)
