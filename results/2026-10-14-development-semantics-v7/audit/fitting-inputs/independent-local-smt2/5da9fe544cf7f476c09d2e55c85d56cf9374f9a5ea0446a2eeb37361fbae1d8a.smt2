(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x305 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (bvadd independent_opaque_1 (_ bv22 32)))))
(let ((?x47 (bvadd (bvsub (bvadd independent_opaque_1 (_ bv1 32)) independent_opaque_0) (_ bv21 32))))
(and (distinct ?x47 ?x305) true))))
(check-sat)
