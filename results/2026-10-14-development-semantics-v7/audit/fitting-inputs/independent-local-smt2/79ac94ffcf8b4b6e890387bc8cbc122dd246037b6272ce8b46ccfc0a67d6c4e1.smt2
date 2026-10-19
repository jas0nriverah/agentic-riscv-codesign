(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x305 (bvadd (bvsub (_ bv0 32) independent_opaque_0) independent_opaque_1)))
(let ((?x1104 (bvsub independent_opaque_1 (bvshl independent_opaque_0 (bvand (_ bv0 32) (_ bv31 32))))))
(and (distinct ?x1104 ?x305) true))))
(check-sat)
