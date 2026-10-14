(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x983 (bvadd independent_opaque_0 (bvsub (_ bv0 32) independent_opaque_1))))
(let ((?x895 (bvsub independent_opaque_0 (bvshl independent_opaque_1 (bvand (_ bv0 32) (_ bv31 32))))))
(and (distinct ?x895 ?x983) true))))
(check-sat)
