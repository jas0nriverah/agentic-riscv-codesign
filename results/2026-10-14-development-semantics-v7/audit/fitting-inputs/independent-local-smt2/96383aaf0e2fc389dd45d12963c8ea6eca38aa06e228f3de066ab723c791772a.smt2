(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x271 (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x52 (bvadd ?x271 independent_opaque_1)))
(let ((?x76 (bvadd independent_opaque_1 ?x271)))
(and (distinct ?x76 ?x52) true)))))
(check-sat)
