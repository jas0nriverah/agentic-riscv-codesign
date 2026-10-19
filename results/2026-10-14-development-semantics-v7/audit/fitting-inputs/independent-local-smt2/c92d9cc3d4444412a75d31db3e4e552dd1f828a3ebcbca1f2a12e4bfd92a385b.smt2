(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x33 (bvadd independent_opaque_1 (_ bv4294966232 32))))
(let ((?x6 (bvadd independent_opaque_0 ?x33)))
(let ((?x43 (bvadd ?x33 independent_opaque_0)))
(and (distinct ?x43 ?x6) true)))))
(check-sat)
