(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x98 (bvadd independent_opaque_1 (_ bv2047 32))))
(let ((?x85 (bvadd (bvsub (_ bv0 32) independent_opaque_0) ?x98)))
(let ((?x1254 (bvsub ?x98 independent_opaque_0)))
(and (distinct ?x1254 ?x85) true)))))
(check-sat)
