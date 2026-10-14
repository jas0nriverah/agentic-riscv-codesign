(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x23 (bvshl independent_opaque_1 (bvand (_ bv24 32) (_ bv31 32)))))
(let ((?x329 (bvadd independent_opaque_0 ?x23)))
(let ((?x72 (bvadd ?x23 independent_opaque_0)))
(and (distinct ?x72 ?x329) true)))))
(check-sat)
