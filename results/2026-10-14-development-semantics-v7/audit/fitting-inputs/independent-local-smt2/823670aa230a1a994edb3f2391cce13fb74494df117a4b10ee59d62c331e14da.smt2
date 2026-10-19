(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1110 (bvadd independent_opaque_0 (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv8 32) (_ bv31 32)))))))
(let ((?x676 (bvshl independent_opaque_1 (bvand (_ bv8 32) (_ bv31 32)))))
(let ((?x624 (bvsub independent_opaque_0 ?x676)))
(and (distinct ?x624 ?x1110) true)))))
(check-sat)
