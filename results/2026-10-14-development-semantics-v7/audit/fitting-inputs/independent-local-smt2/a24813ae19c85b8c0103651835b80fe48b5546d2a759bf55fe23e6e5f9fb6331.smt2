(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x625 (bvadd independent_opaque_1 (_ bv4042322160 32))))
(let ((?x941 (bvsub (bvadd (bvadd independent_opaque_0 independent_opaque_1) (_ bv4042322160 32)) independent_opaque_0)))
(and (distinct ?x941 ?x625) true))))
(check-sat)
