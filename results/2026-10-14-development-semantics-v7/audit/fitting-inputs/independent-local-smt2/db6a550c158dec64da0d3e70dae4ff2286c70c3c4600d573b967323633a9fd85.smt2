(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x33 (bvadd independent_opaque_1 (_ bv4294967295 32))))
(let ((?x703 (bvadd (bvsub (_ bv0 32) independent_opaque_0) ?x33)))
(let ((?x573 (bvsub ?x33 independent_opaque_0)))
(and (distinct ?x573 ?x703) true)))))
(check-sat)
