(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x34 (bvadd (bvshl independent_opaque_0 (bvand (_ bv7 32) (_ bv31 32))) (_ bv18 32))))
(and (distinct ?x34 ?x34) true)))
(check-sat)
