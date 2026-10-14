(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x30 (bvadd independent_opaque_0 independent_opaque_1)))
(let ((?x52 (bvadd independent_opaque_1 independent_opaque_0)))
(and (distinct ?x52 ?x30) true))))
(check-sat)
