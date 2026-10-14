(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x38 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv161 32)))))
(let ((?x13 (bvadd (bvadd independent_opaque_0 (_ bv161 32)) independent_opaque_1)))
(and (distinct ?x13 ?x38) true))))
(check-sat)
