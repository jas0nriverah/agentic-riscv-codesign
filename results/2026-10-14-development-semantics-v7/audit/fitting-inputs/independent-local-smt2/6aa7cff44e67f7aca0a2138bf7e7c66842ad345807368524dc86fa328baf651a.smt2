(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1140 (bvshl independent_opaque_0 (bvand (_ bv13 32) (_ bv31 32)))))
(let ((?x1180 (bvadd ?x1140 independent_opaque_1)))
(let ((?x1257 (bvadd independent_opaque_1 ?x1140)))
(and (distinct ?x1257 ?x1180) true)))))
(check-sat)
