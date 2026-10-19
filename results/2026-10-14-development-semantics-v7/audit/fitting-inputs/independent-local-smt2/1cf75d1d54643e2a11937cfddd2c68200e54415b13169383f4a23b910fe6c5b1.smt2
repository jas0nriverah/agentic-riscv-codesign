(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x385 (bvadd independent_opaque_1 (_ bv63 32))))
(let ((?x983 (bvadd (bvsub (_ bv0 32) independent_opaque_0) ?x385)))
(let ((?x625 (bvsub ?x385 independent_opaque_0)))
(and (distinct ?x625 ?x983) true)))))
(check-sat)
