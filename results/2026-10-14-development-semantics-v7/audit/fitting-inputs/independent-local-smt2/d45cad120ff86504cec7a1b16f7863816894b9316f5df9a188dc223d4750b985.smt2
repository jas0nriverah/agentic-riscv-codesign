(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x676 (bvadd independent_opaque_1 (_ bv16777215 32))))
(let ((?x98 (bvadd (bvsub (_ bv0 32) independent_opaque_0) ?x676)))
(let ((?x983 (bvsub ?x676 independent_opaque_0)))
(and (distinct ?x983 ?x98) true)))))
(check-sat)
