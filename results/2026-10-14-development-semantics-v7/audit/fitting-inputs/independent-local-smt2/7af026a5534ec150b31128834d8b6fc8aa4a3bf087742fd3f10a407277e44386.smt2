(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_2 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x21 (bvadd independent_opaque_0 (bvadd independent_opaque_1 independent_opaque_2))))
(let ((?x19 (bvadd (bvadd independent_opaque_0 independent_opaque_2) independent_opaque_1)))
(and (distinct ?x19 ?x21) true))))
(check-sat)
