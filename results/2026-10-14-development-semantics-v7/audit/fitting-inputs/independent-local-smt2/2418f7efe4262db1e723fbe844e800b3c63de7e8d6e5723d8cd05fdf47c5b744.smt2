(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x23 (bvadd independent_opaque_1 (_ bv63 32))))
(let ((?x14 (bvadd independent_opaque_0 ?x23)))
(let ((?x28 (bvadd ?x23 independent_opaque_0)))
(and (distinct ?x28 ?x14) true)))))
(check-sat)
