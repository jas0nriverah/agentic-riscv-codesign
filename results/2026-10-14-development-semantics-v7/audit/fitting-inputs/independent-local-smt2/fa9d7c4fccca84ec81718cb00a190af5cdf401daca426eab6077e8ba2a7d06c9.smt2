(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x74 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv10 32)))))
(let ((?x13 (bvadd (bvadd independent_opaque_1 independent_opaque_0) (_ bv10 32))))
(and (distinct ?x13 ?x74) true))))
(check-sat)
