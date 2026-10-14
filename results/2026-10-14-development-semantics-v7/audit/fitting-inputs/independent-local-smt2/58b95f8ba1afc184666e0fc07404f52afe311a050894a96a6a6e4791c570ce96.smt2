(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x13 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv16 32)))))
(let ((?x65 (bvadd (bvadd independent_opaque_0 independent_opaque_1) (_ bv16 32))))
(and (distinct ?x65 ?x13) true))))
(check-sat)
