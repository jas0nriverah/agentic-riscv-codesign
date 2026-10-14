(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1180 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv24 32) (_ bv31 32)))) independent_opaque_1)))
(let ((?x385 (bvshl independent_opaque_0 (bvand (_ bv24 32) (_ bv31 32)))))
(let ((?x983 (bvsub independent_opaque_1 ?x385)))
(and (distinct ?x983 ?x1180) true)))))
(check-sat)
