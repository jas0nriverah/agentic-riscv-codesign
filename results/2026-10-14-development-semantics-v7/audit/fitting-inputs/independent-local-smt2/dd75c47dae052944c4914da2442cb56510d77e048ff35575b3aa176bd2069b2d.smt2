(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x703 (bvadd independent_opaque_1 (_ bv129 32))))
(let ((?x664 (bvsub (bvadd (bvadd independent_opaque_0 independent_opaque_1) (_ bv129 32)) independent_opaque_0)))
(and (distinct ?x664 ?x703) true))))
(check-sat)
