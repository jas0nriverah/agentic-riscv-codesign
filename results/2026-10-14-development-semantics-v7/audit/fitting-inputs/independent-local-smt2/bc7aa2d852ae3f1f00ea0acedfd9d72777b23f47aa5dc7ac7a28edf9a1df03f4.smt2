(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x809 (bvadd independent_opaque_1 (_ bv5 32))))
(let ((?x385 (bvsub (bvadd (bvadd independent_opaque_0 independent_opaque_1) (_ bv5 32)) independent_opaque_0)))
(and (distinct ?x385 ?x809) true))))
(check-sat)
