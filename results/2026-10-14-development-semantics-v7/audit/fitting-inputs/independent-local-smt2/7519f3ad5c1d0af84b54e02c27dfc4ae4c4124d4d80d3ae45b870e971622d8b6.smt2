(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x24 (bvadd independent_opaque_0 (bvadd (bvsub (_ bv0 32) independent_opaque_1) (_ bv5 32)))))
(let ((?x1196 (bvadd (bvsub independent_opaque_0 independent_opaque_1) (_ bv5 32))))
(and (distinct ?x1196 ?x24) true))))
(check-sat)
