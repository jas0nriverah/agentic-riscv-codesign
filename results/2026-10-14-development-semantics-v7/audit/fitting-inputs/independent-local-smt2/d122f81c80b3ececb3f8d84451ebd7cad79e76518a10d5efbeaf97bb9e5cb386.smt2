(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x958 (bvshl independent_opaque_0 (bvand (_ bv10 32) (_ bv31 32)))))
(let ((?x525 (bvadd ?x958 independent_opaque_1)))
(let ((?x756 (bvadd independent_opaque_1 ?x958)))
(and (distinct ?x756 ?x525) true)))))
(check-sat)
