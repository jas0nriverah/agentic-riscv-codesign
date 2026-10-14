(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x13 (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32)))))
(let ((?x65 (bvadd ?x13 independent_opaque_1)))
(let ((?x44 (bvadd independent_opaque_1 ?x13)))
(and (distinct ?x44 ?x65) true)))))
(check-sat)
