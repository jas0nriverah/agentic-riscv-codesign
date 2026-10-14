(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x113 (bvadd independent_opaque_0 (bvadd (bvsub (_ bv0 32) independent_opaque_1) (_ bv2047 32)))))
(let ((?x1141 (bvsub (bvadd independent_opaque_0 (_ bv2047 32)) independent_opaque_1)))
(and (distinct ?x1141 ?x113) true))))
(check-sat)
