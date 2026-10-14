(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x703 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (bvadd independent_opaque_1 (_ bv15 32)))))
(let ((?x113 (bvadd (bvsub independent_opaque_1 independent_opaque_0) (_ bv15 32))))
(and (distinct ?x113 ?x703) true))))
(check-sat)
