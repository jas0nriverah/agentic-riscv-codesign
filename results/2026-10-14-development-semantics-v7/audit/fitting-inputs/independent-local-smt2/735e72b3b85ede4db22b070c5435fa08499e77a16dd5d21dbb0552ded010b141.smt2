(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x556 (bvadd independent_opaque_0 (_ bv18 32))))
(let ((?x334 (bvadd (bvadd independent_opaque_0 (_ bv0 32)) (_ bv18 32))))
(and (distinct ?x334 ?x556) true))))
(check-sat)
