(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x514 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv64 32)))))
(let ((?x1265 (bvadd (bvadd independent_opaque_0 independent_opaque_1) (_ bv64 32))))
(and (distinct ?x1265 ?x514) true))))
(check-sat)
