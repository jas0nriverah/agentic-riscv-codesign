(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x356 (bvadd independent_opaque_1 (_ bv4294967295 32))))
(let ((?x664 (bvadd (bvsub (_ bv0 32) independent_opaque_0) ?x356)))
(let ((?x66 (bvsub ?x356 independent_opaque_0)))
(and (distinct ?x66 ?x664) true)))))
(check-sat)
