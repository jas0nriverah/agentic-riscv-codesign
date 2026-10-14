(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x44 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv8 32) (_ bv31 32)))) independent_opaque_1)))
(let ((?x843 (bvshl independent_opaque_0 (bvand (_ bv8 32) (_ bv31 32)))))
(let ((?x446 (bvsub independent_opaque_1 ?x843)))
(and (distinct ?x446 ?x44) true)))))
(check-sat)
