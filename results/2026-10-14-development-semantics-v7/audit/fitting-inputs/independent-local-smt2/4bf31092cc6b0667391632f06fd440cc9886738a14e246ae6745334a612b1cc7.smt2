(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x428 (bvadd (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32))) (_ bv3 32))))
(and (distinct ?x428 ?x428) true)))
(check-sat)
