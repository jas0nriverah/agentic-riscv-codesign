(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x446 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (_ bv63 32))))
(let ((?x1196 (bvsub (bvadd (_ bv0 32) (_ bv63 32)) independent_opaque_0)))
(and (distinct ?x1196 ?x446) true))))
(check-sat)
