(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x23 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv26 32)))))
(let ((?x424 (bvadd (bvadd independent_opaque_0 independent_opaque_1) (_ bv26 32))))
(and (distinct ?x424 ?x23) true))))
(check-sat)
