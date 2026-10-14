(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_2 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x271 (bvadd independent_opaque_2 (_ bv1 32))))
(let ((?x49 (bvadd (bvadd independent_opaque_0 independent_opaque_1) ?x271)))
(let ((?x79 (bvadd independent_opaque_0 (bvadd independent_opaque_1 ?x271))))
(and (distinct ?x79 ?x49) true)))))
(check-sat)
