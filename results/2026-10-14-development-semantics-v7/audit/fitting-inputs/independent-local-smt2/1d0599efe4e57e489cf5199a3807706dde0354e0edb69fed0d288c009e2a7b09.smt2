(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1159 (bvadd independent_opaque_0 (bvadd (bvsub (_ bv0 32) independent_opaque_1) (_ bv8 32)))))
(let ((?x664 (bvsub (bvadd independent_opaque_0 (_ bv8 32)) independent_opaque_1)))
(and (distinct ?x664 ?x1159) true))))
(check-sat)
