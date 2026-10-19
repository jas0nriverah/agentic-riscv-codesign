(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x38 (bvadd independent_opaque_1 (_ bv4294966072 32))))
(let ((?x35 (bvadd independent_opaque_0 ?x38)))
(let ((?x37 (bvadd ?x38 independent_opaque_0)))
(and (distinct ?x37 ?x35) true)))))
(check-sat)
