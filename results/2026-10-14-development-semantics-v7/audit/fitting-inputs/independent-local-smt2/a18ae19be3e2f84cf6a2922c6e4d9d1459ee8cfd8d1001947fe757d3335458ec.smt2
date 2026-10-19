(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x385 (bvadd independent_opaque_0 (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32)))))))
(let ((?x756 (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x1180 (bvsub independent_opaque_0 ?x756)))
(and (distinct ?x1180 ?x385) true)))))
(check-sat)
