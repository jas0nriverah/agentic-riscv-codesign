(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x25 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (bvadd independent_opaque_1 (_ bv25 32)))))
(let ((?x703 (bvadd (bvsub independent_opaque_1 independent_opaque_0) (_ bv25 32))))
(and (distinct ?x703 ?x25) true))))
(check-sat)
