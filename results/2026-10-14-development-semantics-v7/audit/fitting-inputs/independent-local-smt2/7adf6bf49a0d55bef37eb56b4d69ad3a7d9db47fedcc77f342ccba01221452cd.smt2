(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1141 (bvadd independent_opaque_0 (_ bv17 32))))
(let ((?x66 (bvadd (bvshl independent_opaque_0 (bvand (_ bv0 32) (_ bv31 32))) (_ bv17 32))))
(and (distinct ?x66 ?x1141) true))))
(check-sat)
