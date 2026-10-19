(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x222 (bvshl independent_opaque_0 (bvand (_ bv25 32) (_ bv31 32)))))
(let ((?x756 (bvadd ?x222 independent_opaque_1)))
(let ((?x82 (bvadd independent_opaque_1 ?x222)))
(and (distinct ?x82 ?x756) true)))))
(check-sat)
