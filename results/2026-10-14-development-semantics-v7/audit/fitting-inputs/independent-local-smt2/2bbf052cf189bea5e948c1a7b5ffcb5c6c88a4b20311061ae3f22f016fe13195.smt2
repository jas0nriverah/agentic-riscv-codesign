(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x47 (bvadd independent_opaque_0 (bvadd (bvsub (_ bv0 32) independent_opaque_1) (_ bv64 32)))))
(let ((?x305 (bvadd (bvsub independent_opaque_0 independent_opaque_1) (_ bv64 32))))
(and (distinct ?x305 ?x47) true))))
(check-sat)
