(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x8 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv4294966072 32)))))
(let ((?x23 (bvadd (bvadd independent_opaque_0 (_ bv4294966072 32)) independent_opaque_1)))
(and (distinct ?x23 ?x8) true))))
(check-sat)
