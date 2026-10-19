(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x305 (bvadd (bvshl independent_opaque_0 (bvand (_ bv16 32) (_ bv31 32))) (bvshl independent_opaque_1 (bvand (_ bv16 32) (_ bv31 32))))))
(let ((?x85 (bvand (_ bv16 32) (_ bv31 32))))
(let ((?x10 (bvshl (bvadd independent_opaque_0 independent_opaque_1) ?x85)))
(and (distinct ?x10 ?x305) true)))))
(check-sat)
