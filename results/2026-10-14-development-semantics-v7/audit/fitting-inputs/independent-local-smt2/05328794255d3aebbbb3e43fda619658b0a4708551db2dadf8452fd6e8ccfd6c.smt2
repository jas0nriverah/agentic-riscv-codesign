(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x113 (bvadd (bvshl independent_opaque_0 (bvand (_ bv6 32) (_ bv31 32))) (_ bv65 32))))
(and (distinct ?x113 ?x113) true)))
(check-sat)
