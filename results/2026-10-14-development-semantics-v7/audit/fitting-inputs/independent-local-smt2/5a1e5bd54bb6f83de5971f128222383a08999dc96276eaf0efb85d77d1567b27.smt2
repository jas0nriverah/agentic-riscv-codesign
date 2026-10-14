(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x5 (bvadd independent_opaque_1 (_ bv4294966296 32))))
(let ((?x8 (bvadd independent_opaque_0 ?x5)))
(let ((?x35 (bvadd ?x5 independent_opaque_0)))
(and (distinct ?x35 ?x8) true)))))
(check-sat)
