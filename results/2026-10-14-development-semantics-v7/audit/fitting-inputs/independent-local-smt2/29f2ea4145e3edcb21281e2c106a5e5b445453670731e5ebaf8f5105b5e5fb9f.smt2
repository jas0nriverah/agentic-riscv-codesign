(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1104 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (_ bv32 32))))
(let ((?x744 (bvsub (bvadd (_ bv0 32) (_ bv32 32)) independent_opaque_0)))
(and (distinct ?x744 ?x1104) true))))
(check-sat)
