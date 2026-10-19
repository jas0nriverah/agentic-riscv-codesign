(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x222 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv129 32)))))
(let ((?x525 (bvadd (bvadd independent_opaque_1 independent_opaque_0) (_ bv129 32))))
(and (distinct ?x525 ?x222) true))))
(check-sat)
