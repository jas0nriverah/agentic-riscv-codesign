(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x10 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv31 32) (_ bv31 32)))) (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv31 32) (_ bv31 32)))))))
(let ((?x1141 (bvand (_ bv31 32) (_ bv31 32))))
(let ((?x996 (bvshl (bvadd independent_opaque_0 independent_opaque_1) ?x1141)))
(and (distinct ?x996 ?x10) true)))))
(check-sat)
