(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1180 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv1 32)))))
(let ((?x255 (bvadd (bvadd independent_opaque_0 independent_opaque_1) (_ bv1 32))))
(and (distinct ?x255 ?x1180) true))))
(check-sat)
