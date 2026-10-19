(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x42 (bvadd independent_opaque_0 (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv13 32) (_ bv31 32)))))))
(let ((?x996 (bvshl independent_opaque_1 (bvand (_ bv13 32) (_ bv31 32)))))
(let ((?x276 (bvsub independent_opaque_0 ?x996)))
(and (distinct ?x276 ?x42) true)))))
(check-sat)
