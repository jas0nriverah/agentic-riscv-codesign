(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1254 (bvadd independent_opaque_1 (_ bv4294967295 32))))
(let ((?x391 (bvadd (bvsub (_ bv0 32) independent_opaque_0) ?x1254)))
(let ((?x385 (bvsub ?x1254 independent_opaque_0)))
(and (distinct ?x385 ?x391) true)))))
(check-sat)
