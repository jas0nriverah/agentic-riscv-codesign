(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1141 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (_ bv1054 32))))
(let ((?x47 (bvsub (bvadd (_ bv0 32) (_ bv1054 32)) independent_opaque_0)))
(and (distinct ?x47 ?x1141) true))))
(check-sat)
